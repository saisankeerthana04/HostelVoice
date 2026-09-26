"""
Sarvam AI API wrappers for HostelVoice.

Two capabilities are used:
  1. Speech-to-Text  (saarika:v2)  - converts the student's voice recording
     (English / Hindi / Tamil / code-mixed) into text.
  2. Chat / LLM      (sarvam-m)    - understands the complaint text and
     returns structured fields as strict JSON.

If SARVAM_API_KEY is not set, both functions fall back to a realistic
demo mode (canned transcript + rule-based extraction) so the app can be
demonstrated end-to-end without any credentials.
"""

import json
import os
import re

import requests

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "").strip()
STT_MODEL = os.environ.get("SARVAM_STT_MODEL", "saaras:v3")
CHAT_MODEL = os.environ.get("SARVAM_CHAT_MODEL", "sarvam-105b")

STT_URL = "https://api.sarvam.ai/speech-to-text"
CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"

API_KEY_PRESENT = bool(SARVAM_API_KEY)


# ---------------------------------------------------------------------------
# Speech-to-text
# ---------------------------------------------------------------------------

def transcribe_audio(audio_bytes: bytes, filename: str = "recording.wav") -> dict:
    """Send the recorded audio to Sarvam Speech-to-Text."""

    if not API_KEY_PRESENT:
        return {
            "transcript": "Room 312-la fan work aagala, nethu lendhu problem.",
            "language": "demo",
            "demo": True,
        }

    files = {"file": (filename, audio_bytes, "audio/wav")}
    data = {
        "model": STT_MODEL,
        "language_code": "unknown",
        "mode": "transcribe",
    }

    resp = requests.post(
        STT_URL,
        headers={"api-subscription-key": SARVAM_API_KEY},
        files=files,
        data=data,
        timeout=60,
    )

    print("SARVAM STATUS:", resp.status_code)
    print("SARVAM RESPONSE:", resp.text)

    resp.raise_for_status()
    result = resp.json()

    transcript = result.get("transcript", "")

    return {
        "transcript": transcript,
        "language": result.get("language_code", "unknown"),
        "demo": False,
    }


# ---------------------------------------------------------------------------
# Complaint understanding (LLM)
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """\
You are the complaint-parsing engine of a hostel complaint system in India.
The student's complaint may be in English, Hindi, Tamil, or code-mixed
Indian languages (e.g. Tanglish such as "Room 312-la fan work aagala").

Extract the following fields from the complaint:
- student_name: the student's name if mentioned, else ""
- room_number: the room number (digits only if possible), else ""
- category: exactly one of "Electrical", "Plumbing", "Wi-Fi", "Room Maintenance", "Cleanliness", "Other"
- description: a short, clear ENGLISH description of the problem
- duration: how long the problem has existed, in English (e.g. "Since yesterday"), else ""
- priority: "High" (safety hazard, no water, blocked toilet, many students affected),
  "Medium" (basic facility broken, e.g. fan not working), or
  "Low" (cosmetic / cleanliness / minor inconvenience)

Respond with ONLY a valid JSON object with exactly these six keys.
No explanations, no markdown, no code fences.
"""


def extract_fields(text: str) -> dict:
    """Use the Sarvam LLM to turn a free-text complaint into structured fields.

    Returns {"student_name", "room_number", "category", "description",
             "duration", "priority", "demo"}.
    """
    if not API_KEY_PRESENT:
        return _rule_based_extract(text)

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Complaint: {text}"},
        ],
        "temperature": 0.2,
        "max_tokens": 500,
        "reasoning_effort":None,
    }
    resp = requests.post(
        CHAT_URL,
        headers={
            "Authorization": f"Bearer {SARVAM_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _parse_llm_json(content)


def _parse_llm_json(content: str) -> dict:
    """Parse the model output, tolerating stray markdown fences."""
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return _empty_fields()
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return _empty_fields()

    categories = {"Electrical", "Plumbing", "Wi-Fi", "Room Maintenance",
                  "Cleanliness", "Other"}
    priorities = {"High", "Medium", "Low"}

    category = str(data.get("category", "Other")).strip() or "Other"
    if category not in categories:
        category = "Other"
    priority = str(data.get("priority", "Medium")).strip().capitalize()
    if priority not in priorities:
        priority = "Medium"

    return {
        "student_name": str(data.get("student_name", "")).strip(),
        "room_number": str(data.get("room_number", "")).strip(),
        "category": category,
        "description": str(data.get("description", "")).strip(),
        "duration": str(data.get("duration", "")).strip(),
        "priority": priority,
        "demo": False,
    }


def _empty_fields() -> dict:
    return {
        "student_name": "",
        "room_number": "",
        "category": "Other",
        "description": "",
        "duration": "",
        "priority": "Medium",
        "demo": False,
    }


# ---------------------------------------------------------------------------
# Demo-mode fallback extraction (no API key configured)
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS = [
    (("wifi", "wi-fi", "internet", "network"), "Wi-Fi"),
    (("fan", "light", "switch", "electrical", "current", "shock",
      "plug", "socket", "tubelight", "lamp", "bulb", "power"), "Electrical"),
    (("water", "tap", "leak", "toilet", "bathroom", "pipe", "drain",
      "flush", "geyser", "sink", "blocked", "overflow", "paani", "pani",
      "nahi aa raha"), "Plumbing"),
    (("clean", "dirty", "dust", "garbage", "trash", "smell", "sweep",
      "mop", "waste", "hygiene"), "Cleanliness"),
    (("door", "window", "bed", "table", "chair", "lock", "key", "wall",
      "ceiling", "paint", "broken"), "Room Maintenance"),
]

_DURATION_PATTERNS = [
    (r"\bnethu\b|\byesterday\b|\bkal\b", "Since yesterday"),
    (r"(\w+)\s*(?:days?|naal|naalgal|din)\b", None),  # handled specially
]

_HIGH_PRIORITY_WORDS = (
    "urgent", "immediately", "right now", "emergency", "shock", "fire",
    "flood", "overflow", "astama", "romba", "no water", "blocked",
)


def _rule_based_extract(text: str) -> dict:
    """Best-effort extraction used in demo mode (no LLM available).

    Handles the showcase example ("Room 312-la fan work aagala, nethu
    lendu problem.") and simple English/Hindi/Tanglish complaints.
    """
    t = text.lower()

    # Room number: "room 312", "312-la", "312 la", "oota no 312"
    room = ""
    m = re.search(r"\broom\s*(?:no\.?\s*)?(\d{1,4})", t)
    if not m:
        m = re.search(r"\b(\d{2,4})\s*(?:-|–)?\s*(?:la|il|le|lla|me|laa)\b", t)
    if not m:
        m = re.search(r"\b(?:no|number)\s*(\d{1,4})\b", t)
    if m:
        room = m.group(1)

    # Category by keyword scan (first match wins, ordered by specificity)
    category = "Other"
    for keywords, label in _CATEGORY_KEYWORDS:
        if any(k in t for k in keywords):
            category = label
            break

    # Duration
    duration = ""
    if re.search(r"\bnethu\b|\byesterday\b|\bkal\b", t):
        duration = "Since yesterday"
    else:
        m = re.search(r"(\d+|one|two|three|four|five|six|seven|eight|nine|"
                      r"ten|rendu|moonu|nalu|ek|do|teen|char)\s*"
                      r"(?:days?|din|dino|naal|naalgal)", t)
        if m:
            word_to_num = {"one": "1", "two": "2", "three": "3", "four": "4",
                           "five": "5", "six": "6", "seven": "7", "eight": "8",
                           "nine": "9", "ten": "10", "rendu": "2", "moonu": "3",
                           "nalu": "4", "ek": "1", "do": "2", "teen": "3",
                           "char": "4"}
            count = word_to_num.get(m.group(1), m.group(1))
            duration = f"For {count} days"
        elif re.search(r"\bthis morning\b|\bkalai\b|\bearly morning\b", t):
            duration = "Since this morning"
        elif re.search(r"\btoday\b|\binru\b|\baaj\b", t):
            duration = "Since today"
        elif re.search(r"\bweek\b|\bvaram\b|\bhafte\b", t):
            duration = "Since last week"

    # Priority
    if any(w in t for w in _HIGH_PRIORITY_WORDS):
        priority = "High"
    elif category == "Cleanliness":
        priority = "Low"
    else:
        priority = "Medium"

    # Student name: "my name is X" / "naan X" / "I am X"
    name = ""
    m = re.search(r"(?:my name is|i am|i'm|this is|naan)\s+([a-z]+(?:\s+[a-z]+)?)",
                  t, flags=re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        if candidate.lower() not in ("having", "facing", "staying", "from"):
            name = candidate.title()

    # Description: cleaned-up original text
    description = text.strip()
    if len(description) > 220:
        description = description[:217] + "..."

    return {
        "student_name": name,
        "room_number": room,
        "category": category,
        "description": description,
        "duration": duration,
        "priority": priority,
        "demo": True,
    }
