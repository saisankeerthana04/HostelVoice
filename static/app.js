/* app.js — student-side flow: record → transcribe → AI extract → submit → track */

const $ = (id) => document.getElementById(id);

const els = {
  recordBtn: $("recordBtn"), recordStatus: $("recordStatus"),
  recordTimer: $("recordTimer"), audioPreview: $("audioPreview"),
  complaintText: $("complaintText"), transcribeBtn: $("transcribeBtn"),
  step1: $("step1"), step1Error: $("step1Error"),
  step2: $("step2"), step2Error: $("step2Error"), step3: $("step3"),
  transcriptView: $("transcriptView"), langBadge: $("langBadge"),
  fName: $("fName"), fRoom: $("fRoom"), fCategory: $("fCategory"),
  fPriority: $("fPriority"), fDesc: $("fDesc"), fDuration: $("fDuration"),
  submitBtn: $("submitBtn"), ticketId: $("ticketId"),
  ticketPreview: $("ticketPreview"), newComplaintBtn: $("newComplaintBtn"),
  trackInput: $("trackInput"), trackBtn: $("trackBtn"), trackResult: $("trackResult"),
};

let lastAudioBlob = null;
let originalText = "";

/* ---------- helpers ---------- */

function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}
function hideError(el) { el.classList.add("hidden"); }

function setBusy(btn, busy, label) {
  btn.disabled = busy;
  btn.dataset.origLabel = btn.dataset.origLabel || btn.textContent;
  btn.textContent = busy ? label : btn.dataset.origLabel;
}

function statusPill(status) {
  const cls = { "Submitted": "submitted", "In Progress": "inprogress",
                "Resolved": "resolved" }[status] || "submitted";
  return `<span class="pill ${cls}">${status}</span>`;
}

/* ---------- step 1: recording ---------- */

let timerInterval = null;
let seconds = 0;

async function toggleRecording() {
  if (!VoiceRecorder.isRecording()) {
    try {
      await VoiceRecorder.start();
    } catch (err) {
      showError(els.step1Error,
        "Could not access the microphone. Use a Chrome/Edge browser and " +
        "allow mic permission, or type your complaint below instead.");
      return;
    }
    lastAudioBlob = null;
    els.audioPreview.hidden = true;
    hideError(els.step1Error);
    els.recordBtn.classList.add("recording");
    els.recordStatus.textContent = "Recording… tap again to stop";
    seconds = 0;
    els.recordTimer.textContent = "00:00";
    timerInterval = setInterval(() => {
      seconds++;
      els.recordTimer.textContent =
        String(Math.floor(seconds / 60)).padStart(2, "0") + ":" +
        String(seconds % 60).padStart(2, "0");
    }, 1000);
  } else {
    clearInterval(timerInterval);
    els.recordBtn.classList.remove("recording");
    els.recordStatus.textContent = "Processing recording…";
    const blob = await VoiceRecorder.stop();
    if (blob && blob.size > 3000) {
      lastAudioBlob = blob;
      els.audioPreview.src = URL.createObjectURL(blob);
      els.audioPreview.hidden = false;
      els.recordStatus.textContent = "Recording ready — tap Transcribe.";
    } else {
      els.recordStatus.textContent = "Recording too short — try again.";
    }
    els.transcribeBtn.disabled = !(lastAudioBlob || els.complaintText.value.trim());
  }
}

els.recordBtn.addEventListener("click", toggleRecording);

els.complaintText.addEventListener("input", () => {
  els.transcribeBtn.disabled =
    !(els.complaintText.value.trim() || lastAudioBlob);
});

/* ---------- transcribe + understand ---------- */

els.transcribeBtn.addEventListener("click", async () => {
  hideError(els.step1Error);
  setBusy(els.transcribeBtn, true, "Transcribing…");

  let text = els.complaintText.value.trim();
  let language = "";

  try {
    if (!text && lastAudioBlob) {
      const form = new FormData();
      form.append("audio", lastAudioBlob, "recording.wav");
      const res = await fetch("/api/transcribe", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Transcription failed.");
      text = data.transcript;
      language = data.language;
    } else {
      language = "typed";
    }

    if (!text) throw new Error("Nothing to transcribe.");

    // Second stage: AI understanding
    setBusy(els.transcribeBtn, true, "AI is understanding…");
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const fields = await res.json();
    if (!res.ok) throw new Error(fields.error || "Understanding failed.");

    originalText = text;
    fillForm(text, language, fields);
    els.step2.classList.remove("hidden");
    els.step3.classList.add("hidden");
    els.step2.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    showError(els.step1Error, err.message);
  } finally {
    setBusy(els.transcribeBtn, false);
  }
});

function fillForm(text, language, f) {
  els.transcriptView.value = text;
  els.langBadge.textContent =
    language === "typed" ? "Typed input" : `Detected language: ${language}`;
  els.fName.value = f.student_name || "";
  els.fRoom.value = f.room_number || "";
  els.fCategory.value = f.category || "Other";
  els.fPriority.value = f.priority || "Medium";
  els.fDesc.value = f.description || "";
  els.fDuration.value = f.duration || "";
}

/* ---------- submit ---------- */

els.submitBtn.addEventListener("click", async () => {
  hideError(els.step2Error);
  if (!els.fDesc.value.trim()) {
    showError(els.step2Error, "Please describe the problem before submitting.");
    return;
  }
  setBusy(els.submitBtn, true, "Submitting…");
  try {
    const res = await fetch("/api/complaints", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_name: els.fName.value,
        room_number: els.fRoom.value,
        category: els.fCategory.value,
        description: els.fDesc.value,
        duration: els.fDuration.value,
        priority: els.fPriority.value,
        original_text: originalText,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Submission failed.");

    const c = data.complaint;
    els.ticketId.textContent = c.ticket_id;
    els.ticketPreview.innerHTML = `
      <div><strong>Ticket ID</strong> ${c.ticket_id}</div>
      <div><strong>Student</strong> ${c.student_name || "—"}</div>
      <div><strong>Room</strong> ${c.room_number || "—"}</div>
      <div><strong>Category</strong> ${c.category}</div>
      <div><strong>Priority</strong> ${c.priority}</div>
      <div><strong>Description</strong> ${c.description}</div>
      <div><strong>Duration</strong> ${c.duration || "—"}</div>
      <div><strong>Submitted at</strong> ${c.created_at}</div>`;
    els.step3.classList.remove("hidden");
    els.step3.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    showError(els.step2Error, err.message);
  } finally {
    setBusy(els.submitBtn, false);
  }
});

els.newComplaintBtn.addEventListener("click", () => {
  els.step2.classList.add("hidden");
  els.step3.classList.add("hidden");
  els.complaintText.value = "";
  lastAudioBlob = null;
  els.audioPreview.hidden = true;
  els.recordStatus.textContent = "Tap the mic to start recording";
  els.recordTimer.textContent = "00:00";
  els.transcribeBtn.disabled = true;
  window.scrollTo({ top: 0, behavior: "smooth" });
});

/* ---------- track status ---------- */

async function checkStatus() {
  const id = els.trackInput.value.trim();
  els.trackResult.classList.remove("hidden");
  if (!id) {
    els.trackResult.innerHTML = `<p class="error">Please enter a ticket ID.</p>`;
    return;
  }
  els.trackResult.innerHTML = `<p class="muted">Checking…</p>`;
  try {
    const res = await fetch(`/api/complaints/${encodeURIComponent(id)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Lookup failed.");
    const c = data.complaint;
    els.trackResult.innerHTML = `
      <div class="ticket-preview">
        <div><strong>Ticket</strong> ${c.ticket_id} &nbsp; ${statusPill(c.status)}</div>
        <div><strong>Room</strong> ${c.room_number || "—"}</div>
        <div><strong>Category</strong> ${c.category}</div>
        <div><strong>Description</strong> ${c.description}</div>
        <div><strong>Priority</strong> ${c.priority}</div>
        <div><strong>Submitted</strong> ${c.created_at}</div>
        <div><strong>Last updated</strong> ${c.updated_at}</div>
      </div>`;
  } catch (err) {
    els.trackResult.innerHTML = `<p class="error">${err.message}</p>`;
  }
}

els.trackBtn.addEventListener("click", checkStatus);
els.trackInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") checkStatus();
});
