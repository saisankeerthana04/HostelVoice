# HostelVoice – AI Hostel Complaint Assistant

Hostel students can **speak** their complaint in English, Tamil, Hindi, or
code-mixed Indian languages (e.g. Tanglish). Sarvam AI converts the speech
to text, an LLM extracts structured details, the student reviews and
confirms, and a ticket lands on the **Hostel Office Dashboard**, where the
office can move it through *Submitted → In Progress → Resolved*.

```
Voice complaint → Speech-to-Text → AI understands complaint
→ Structured complaint shown to student → Student confirms
→ Complaint submitted → Ticket ID generated
→ Hostel office dashboard displays complaint → Office updates status
→ Student can see the status
```

## Tech stack

- **Backend:** Python + Flask (single small server, JSON-file storage — no database setup)
- **Frontend:** plain HTML/CSS/JS, mic recording via the Web Audio API (16 kHz mono WAV)
- **Sarvam AI APIs:**
  - **Speech-to-Text** (`saaras:v3`) — multilingual speech recognition
  - **Chat completions** (`sarvam-m`) — understands code-mixed text and returns structured fields as JSON

## Project structure

```
HostelVoice/
├── app.py               # Flask server + REST API
├── sarvam_client.py     # Sarvam API wrappers (STT + LLM) with demo fallbacks
├── requirements.txt
├── .env.example         # required env var names (no real secrets)
├── .gitignore
├── templates/
│   ├── index.html       # student flow (record → review → submit → track)
│   └── dashboard.html   # hostel-office dashboard
└── static/
    ├── style.css
    ├── app.js           # student flow logic
    ├── dashboard.js     # dashboard logic
    └── recorder.js       # mic capture + WAV encoding in the browser
```

## Setup (run locally, e.g. from VS Code)

1. **Prerequisites:** Python 3.10+ and a Chromium-based browser
   (Chrome/Edge — needed for microphone access on `localhost`).

2. Open the project folder in VS Code and create a virtual environment:

   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS / Linux:
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure your Sarvam API key:

   ```bash
   # Windows (PowerShell):
   copy .env.example .env
   # macOS / Linux:
   cp .env.example .env
   ```

   Then edit `.env` and paste your key from https://dashboard.sarvam.ai:

   ```
   SARVAM_API_KEY=your_key_here
   ```

   > **No key? No problem.** Without a key the app runs in **demo mode**:
   > the mic button returns a sample Tanglish complaint
   > (*"Room 312-la fan work aagala, nethu lendu problem."*) and a
   > rule-based parser fills the fields, so the entire flow is still
   > demonstrable end-to-end. A yellow banner indicates demo mode.

5. Run the app:

   ```bash
   python app.py
   ```

6. Open in your browser:
   - Student view: **http://127.0.0.1:5000/**
   - Hostel office dashboard: **http://127.0.0.1:5000/dashboard**

   Tip: open the dashboard in a second browser tab (or another window) and
   keep it visible while you file a complaint from the student tab — it
   auto-refreshes every 5 seconds.

## Demo walkthrough (2–3 minutes)

1. **Student tab** — tap the mic and speak, e.g.
   *"Room 312-la fan work aagala, nethu lendu problem"* (or type it).
2. Click **Transcribe & Understand** — you'll see the transcript and the
   AI-extracted fields: Room 312, Category Electrical, fan not working,
   Since yesterday.
3. Edit anything you like (all fields are editable), then click
   **Submit Complaint**.
4. A ticket ID (e.g. **HV-0001**) is generated and shown.
5. **Dashboard tab** — the complaint appears with room, category,
   description, priority and status. Change the status dropdown from
   *Submitted* to *In Progress* or *Resolved*.
6. Back on the **student tab**, enter the ticket ID under
   **Track your complaint** to see the current status.

## Security notes

- The API key lives only in `.env`, which is listed in `.gitignore` and is
  never sent to the browser — all Sarvam API calls happen server-side.
- `.env.example` documents the variable names without real secrets.
- Submitted complaints are stored in `data/complaints.json` (git-ignored).

## API endpoints (for quick testing with curl)

| Method | Endpoint                | Purpose                                  |
|--------|-------------------------|------------------------------------------|
| POST   | `/api/transcribe`       | audio file → transcript (Sarvam STT)     |
| POST   | `/api/extract`          | text → structured fields (Sarvam LLM)    |
| POST   | `/api/complaints`       | submit a complaint                       |
| GET    | `/api/complaints`       | list all complaints                       |
| GET    | `/api/complaints/<id>`  | get one complaint by ticket ID            |
| PATCH  | `/api/complaints/<id>`  | update status (Submitted / In Progress / Resolved) |
| GET    | `/api/health`           | server + mode check                      |
