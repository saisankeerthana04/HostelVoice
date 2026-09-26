"""
HostelVoice - AI Hostel Complaint Assistant
Flask backend. Run with:  python app.py
"""

import os
import threading
import uuid
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()
import sarvam_client



app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
COMPLAINTS_FILE = os.path.join(DATA_DIR, "complaints.json")

VALID_STATUSES = ["Submitted", "In Progress", "Resolved"]
VALID_CATEGORIES = ["Electrical", "Plumbing", "Wi-Fi", "Room Maintenance",
                     "Cleanliness", "Other"]
VALID_PRIORITIES = ["High", "Medium", "Low"]

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Tiny JSON-file store (persistence across restarts, zero extra deps)
# ---------------------------------------------------------------------------

def _load_complaints():
    if not os.path.exists(COMPLAINTS_FILE):
        return []
    try:
        import json
        with open(COMPLAINTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save_complaints(complaints):
    import json
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(COMPLAINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(complaints, f, indent=2, ensure_ascii=False)


def _next_ticket_id(complaints):
    n = len(complaints) + 1
    return f"HV-{n:04d}"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", sarvam_live=sarvam_client.API_KEY_PRESENT)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# ---------------------------------------------------------------------------
# API: speech-to-text
# ---------------------------------------------------------------------------

@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file received."}), 400
    audio = request.files["audio"]
    try:
        result = sarvam_client.transcribe_audio(audio.read(), audio.filename or "recording.wav")
    except Exception as exc:  # requests errors, upstream errors
        return jsonify({"error": f"Transcription failed: {exc}"}), 502
    if not result["transcript"]:
        return jsonify({"error": "Could not understand the audio. Please try again."}), 422
    return jsonify(result)


# ---------------------------------------------------------------------------
# API: AI extraction
# ---------------------------------------------------------------------------

@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "No complaint text provided."}), 400
    try:
        fields = sarvam_client.extract_fields(text)
    except Exception as exc:
        return jsonify({"error": f"Understanding failed: {exc}"}), 502
    return jsonify(fields)


# ---------------------------------------------------------------------------
# API: complaints (submit / list / status)
# ---------------------------------------------------------------------------

@app.route("/api/complaints", methods=["POST"])
def api_submit_complaint():
    data = request.get_json(silent=True) or {}

    category = data.get("category", "Other")
    priority = data.get("priority", "Medium")
    if category not in VALID_CATEGORIES:
        category = "Other"
    if priority not in VALID_PRIORITIES:
        priority = "Medium"

    description = (data.get("description") or "").strip()
    if not description:
        return jsonify({"error": "Complaint description is required."}), 400

    now = datetime.now()
    with _lock:
        complaints = _load_complaints()
        complaint = {
            "ticket_id": _next_ticket_id(complaints),
            "student_name": (data.get("student_name") or "").strip(),
            "room_number": (data.get("room_number") or "").strip(),
            "category": category,
            "description": description,
            "duration": (data.get("duration") or "").strip(),
            "priority": priority,
            "original_text": (data.get("original_text") or "").strip(),
            "status": "Submitted",
            "created_at": now.strftime("%d %b %Y, %I:%M %p"),
            "updated_at": now.strftime("%d %b %Y, %I:%M %p"),
        }
        complaints.append(complaint)
        _save_complaints(complaints)

    return jsonify({"message": "Complaint submitted successfully.",
                    "complaint": complaint}), 201


@app.route("/api/complaints", methods=["GET"])
def api_list_complaints():
    with _lock:
        complaints = _load_complaints()
    return jsonify({"complaints": complaints})


@app.route("/api/complaints/<ticket_id>", methods=["GET"])
def api_get_complaint(ticket_id):
    ticket_id = ticket_id.strip().upper()
    with _lock:
        complaints = _load_complaints()
    for c in complaints:
        if c["ticket_id"].upper() == ticket_id:
            return jsonify({"complaint": c})
    return jsonify({"error": f"No complaint found for '{ticket_id}'."}), 404


@app.route("/api/complaints/<ticket_id>", methods=["PATCH"])
def api_update_status(ticket_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in VALID_STATUSES:
        return jsonify({"error": f"Status must be one of {VALID_STATUSES}."}), 400

    ticket_id = ticket_id.strip().upper()
    with _lock:
        complaints = _load_complaints()
        for c in complaints:
            if c["ticket_id"].upper() == ticket_id:
                c["status"] = new_status
                c["updated_at"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
                _save_complaints(complaints)
                return jsonify({"message": "Status updated.", "complaint": c})
    return jsonify({"error": f"No complaint found for '{ticket_id}'."}), 404


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "sarvam_live": sarvam_client.API_KEY_PRESENT,
        "mode": "live" if sarvam_client.API_KEY_PRESENT else "demo",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  HostelVoice running at  http://127.0.0.1:{port}")
    print(f"  Student view:            http://127.0.0.1:{port}/")
    print(f"  Hostel office dashboard: http://127.0.0.1:{port}/dashboard\n")
    app.run(host="127.0.0.1", port=port, debug=False)
