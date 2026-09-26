/* dashboard.js — hostel-office view: list complaints, update statuses */

const $ = (id) => document.getElementById(id);
const body = $("complaintsBody");

function priorityPill(p) {
  return `<span class="pill ${p.toLowerCase()}">${p}</span>`;
}

function statusPill(s) {
  const cls = { "Submitted": "submitted", "In Progress": "inprogress",
                "Resolved": "resolved" }[s] || "submitted";
  return `<span class="pill ${cls}">${s}</span>`;
}

function escapeHtml(s) {
  const map = { "&": "amp", "<": "lt", ">": "gt", '"': "quot", "'": "apos" };
  return String(s ?? "").replace(/[&<>"']/g, (c) => "&" + map[c] + ";");
}

async function loadComplaints() {
  try {
    const res = await fetch("/api/complaints");
    const data = await res.json();
    render(data.complaints || []);
  } catch {
    body.innerHTML = `<tr><td colspan="7" class="empty-msg">
      Could not load complaints. Is the server running?</td></tr>`;
  }
}

function render(complaints) {
  const counts = { all: complaints.length };
  for (const s of ["Submitted", "In Progress", "Resolved"])
    counts[s] = complaints.filter((c) => c.status === s).length;

  $("statsRow").innerHTML = `
    <div class="stat-chip"><b>${counts.all}</b><span>Total</span></div>
    <div class="stat-chip"><b>${counts["Submitted"]}</b><span>Submitted</span></div>
    <div class="stat-chip"><b>${counts["In Progress"]}</b><span>In Progress</span></div>
    <div class="stat-chip"><b>${counts["Resolved"]}</b><span>Resolved</span></div>`;

  $("dashCount").textContent = `${counts.all} complaint${counts.all === 1 ? "" : "s"}`;

  if (!complaints.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty-msg">
      No complaints yet. They will appear here as students submit them.</td></tr>`;
    return;
  }

  body.innerHTML = complaints.map((c) => `
    <tr>
      <td><strong>${escapeHtml(c.ticket_id)}</strong></td>
      <td>${escapeHtml(c.room_number || "—")}</td>
      <td>${escapeHtml(c.category)}</td>
      <td>${escapeHtml(c.description)}
          ${c.duration ? `<div class="muted" style="font-size:.78rem">
            ${escapeHtml(c.duration)}</div>` : ""}</td>
      <td>${priorityPill(c.priority)}</td>
      <td>
        <select onchange="updateStatus('${escapeHtml(c.ticket_id)}', this.value)">
          <option ${c.status === "Submitted" ? "selected" : ""}>Submitted</option>
          <option ${c.status === "In Progress" ? "selected" : ""}>In Progress</option>
          <option ${c.status === "Resolved" ? "selected" : ""}>Resolved</option>
        </select>
      </td>
      <td style="white-space:nowrap">${escapeHtml(c.created_at)}</td>
    </tr>`).join("");
}

async function updateStatus(ticketId, newStatus) {
  try {
    const res = await fetch(`/api/complaints/${encodeURIComponent(ticketId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Update failed.");
    loadComplaints();
  } catch (err) {
    alert(`Could not update status: ${err.message}`);
    loadComplaints();
  }
}

$("refreshBtn").addEventListener("click", loadComplaints);

// Auto-refresh every 5 s so newly submitted complaints show up live.
loadComplaints();
setInterval(loadComplaints, 5000);
