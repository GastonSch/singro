const rows = document.getElementById("rows");
const health = document.getElementById("health");
const conn = document.getElementById("conn");

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function render(sessions) {
  if (!sessions.length) {
    rows.innerHTML = '<tr><td colspan="8">Sin sesiones activas.</td></tr>';
    return;
  }
  rows.innerHTML = sessions.map((s) => {
    const stats = s.stats || {};
    const latency = stats.latency_ms != null ? `${Math.round(stats.latency_ms)} ms` : "–";
    const running = s.state === "running";
    return `<tr>
      <td><span class="pill ${escapeHtml(s.state)}">${escapeHtml(s.state)}</span></td>
      <td>${escapeHtml(s.name)}</td>
      <td>${escapeHtml(s.source)} ${s.source_url ? `<small style="color:var(--muted)">${escapeHtml(s.source_url)}</small>` : ""}</td>
      <td>${escapeHtml(s.source_language || "auto")} → ${escapeHtml(s.target_language)}</td>
      <td>${latency}</td>
      <td>${stats.segments ?? 0}</td>
      <td>${stats.errors ?? 0}</td>
      <td>
        <button data-action="${running ? "stop" : "start"}" data-id="${escapeHtml(s.id)}">${running ? "Detener" : "Iniciar"}</button>
        <button class="danger" data-action="delete" data-id="${escapeHtml(s.id)}">Borrar</button>
      </td>
    </tr>`;
  }).join("");
}

rows.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  const { action, id } = button.dataset;
  const url = action === "delete" ? `/api/sessions/${id}` : `/api/sessions/${id}/${action}`;
  await fetch(url, { method: action === "delete" ? "DELETE" : "POST" });
});

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => conn.classList.add("online");
  ws.onclose = () => { conn.classList.remove("online"); setTimeout(connect, 1500); };
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "sessions") render(msg.sessions);
  };
}

fetch("/api/health").then((r) => r.json()).then((h) => {
  health.textContent = `${h.engine} · ${h.model}${h.api_key_configured ? "" : " · sin API key"}`;
}).catch(() => {});

connect();
