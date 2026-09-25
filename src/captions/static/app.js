const state = {
  sessions: [],
  selected: null,
  data: {},
  lang: "both",
};

const els = {
  conn: document.getElementById("conn"),
  engine: document.getElementById("engine-badge"),
  count: document.getElementById("session-count"),
  tabs: document.getElementById("tabs"),
  history: document.getElementById("history"),
  liveOriginal: document.getElementById("live-original"),
  liveTranslation: document.getElementById("live-translation"),
  latency: document.getElementById("stat-latency"),
  segments: document.getElementById("stat-segments"),
  errors: document.getElementById("stat-errors"),
  statState: document.getElementById("stat-state"),
  exportSrt: document.getElementById("export-srt"),
  exportVtt: document.getElementById("export-vtt"),
  exportTxt: document.getElementById("export-txt"),
  overlayLink: document.getElementById("overlay-link"),
  dialog: document.getElementById("add-dialog"),
  form: document.getElementById("add-form"),
  type: document.getElementById("f-type"),
  urlField: document.getElementById("url-field"),
  url: document.getElementById("f-url"),
  sampleList: document.getElementById("sample-list"),
  langToggle: document.getElementById("lang-toggle"),
};

function ensure(id) {
  if (!state.data[id]) state.data[id] = { liveOriginal: "", liveTranslation: "", blocks: [], sourceLanguage: null, stats: {} };
  return state.data[id];
}

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function setConn(online) {
  els.conn.classList.toggle("online", online);
  els.conn.title = online ? "Conectado" : "Reconectando…";
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => setConn(true);
  ws.onclose = () => { setConn(false); setTimeout(connect, 1500); };
  ws.onmessage = (event) => handle(JSON.parse(event.data));
}

function handle(msg) {
  if (msg.type === "sessions") {
    state.sessions = msg.sessions;
    for (const s of state.sessions) ensure(s.id);
    if (!state.selected || !state.sessions.find((s) => s.id === state.selected)) {
      state.selected = state.sessions[0]?.id ?? null;
    }
    renderTabs();
    rebuildHistory();
    renderStats();
    return;
  }
  if (msg.type === "status") {
    const session = state.sessions.find((s) => s.id === msg.session);
    if (session) { session.state = msg.state; session.stats = msg.stats; }
    ensure(msg.session).stats = msg.stats;
    renderTabs();
    if (msg.session === state.selected) renderStats();
    return;
  }
  if (msg.type === "caption") {
    const data = ensure(msg.session);
    if (msg.source_language) data.sourceLanguage = msg.source_language;
    if (msg.lane === "original") data.liveOriginal = msg.text;
    else data.liveTranslation = msg.text;
    if (msg.session === state.selected) updateLive();
    return;
  }
  if (msg.type === "block") {
    const data = ensure(msg.session);
    data.blocks.push({ original: msg.original, translation: msg.translation });
    data.liveOriginal = "";
    data.liveTranslation = "";
    if (msg.session === state.selected) { appendBlock(msg); updateLive(); }
    return;
  }
  if (msg.type === "error") {
    console.warn("error de sesión", msg.session, msg.detail);
    const data = ensure(msg.session);
    if (msg.session === state.selected) {
      els.statState.textContent = "error";
      els.statState.style.color = "var(--error)";
    }
    void data;
  }
}

function renderTabs() {
  els.count.textContent = `${state.sessions.length} sesión${state.sessions.length === 1 ? "" : "es"}`;
  els.tabs.innerHTML = "";
  for (const session of state.sessions) {
    const button = document.createElement("button");
    button.className = "tab" + (session.id === state.selected ? " active" : "");
    button.innerHTML = `<span class="state ${escapeHtml(session.state)}"></span>${escapeHtml(session.name)}`;
    button.onclick = () => selectSession(session.id);
    els.tabs.appendChild(button);
  }
}

function selectSession(id) {
  state.selected = id;
  renderTabs();
  rebuildHistory();
  renderStats();
}

function blockNode(block) {
  const node = document.createElement("div");
  node.className = "block";
  node.innerHTML =
    `<div class="original">${escapeHtml(block.original)}</div>` +
    `<div class="translation">${escapeHtml(block.translation)}</div>`;
  return node;
}

function rebuildHistory() {
  els.history.innerHTML = "";
  const data = state.selected ? state.data[state.selected] : null;
  if (!data) { updateLive(); return; }
  for (const block of data.blocks.slice(-200)) els.history.appendChild(blockNode(block));
  updateLive();
  scrollBottom();
}

function appendBlock(block) {
  els.history.appendChild(blockNode(block));
  if (els.history.childElementCount > 400) els.history.firstElementChild.remove();
  scrollBottom();
}

function updateLive() {
  const data = state.selected ? state.data[state.selected] : null;
  els.liveOriginal.textContent = data?.liveOriginal ?? "";
  els.liveTranslation.textContent = data?.liveTranslation ?? "";
}

function scrollBottom() {
  const container = document.getElementById("captions");
  container.scrollTop = container.scrollHeight;
}

function renderStats() {
  const session = state.sessions.find((s) => s.id === state.selected);
  const data = state.selected ? ensure(state.selected) : null;
  const stats = session?.stats ?? data?.stats ?? {};
  els.latency.textContent = stats.latency_ms != null ? `${Math.round(stats.latency_ms)} ms` : "–";
  els.segments.textContent = stats.segments ?? 0;
  els.errors.textContent = stats.errors ?? 0;
  els.statState.textContent = session?.state ?? "–";
  els.statState.style.color = "";
  const base = state.selected ? `/api/sessions/${encodeURIComponent(state.selected)}/transcript` : "#";
  els.exportSrt.href = `${base}?format=srt&lang=${state.lang}`;
  els.exportVtt.href = `${base}?format=vtt&lang=${state.lang}`;
  els.exportTxt.href = `${base}?format=txt&lang=${state.lang}`;
  els.overlayLink.href = state.selected ? `/overlay?session=${encodeURIComponent(state.selected)}&lang=${state.lang}` : "#";
}

function cycleLang() {
  state.lang = state.lang === "both" ? "translation" : state.lang === "translation" ? "original" : "both";
  const labels = { both: "ES + original", translation: "Solo ES", original: "Solo original" };
  els.langToggle.textContent = labels[state.lang];
  document.body.dataset.lang = state.lang;
  renderStats();
}

async function loadSamples() {
  try {
    const response = await fetch("/api/samples");
    if (!response.ok) return;
    const samples = await response.json();
    els.sampleList.innerHTML = samples.map((s) => `<option value="${escapeHtml(s)}"></option>`).join("");
  } catch { /* ignore */ }
}

els.langToggle.onclick = cycleLang;
document.getElementById("add-session").onclick = () => els.dialog.showModal();
document.getElementById("cancel-add").onclick = () => els.dialog.close();
els.type.onchange = () => { els.urlField.style.display = els.type.value === "mic" ? "none" : "flex"; };
els.form.onsubmit = async (event) => {
  event.preventDefault();
  const payload = {
    id: document.getElementById("f-id").value.trim(),
    name: document.getElementById("f-name").value.trim(),
    source: {
      type: els.type.value,
      url: els.url.value.trim(),
      realtime: true,
      loop: document.getElementById("f-loop").checked,
    },
    source_language: document.getElementById("f-src").value || null,
    target_language: document.getElementById("f-target").value,
  };
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.ok) {
    els.dialog.close();
    els.form.reset();
  } else {
    alert(`No se pudo crear la sesión: ${await response.text()}`);
  }
};

fetch("/api/health").then((r) => r.json()).then((h) => {
  els.engine.textContent = `${h.engine}${h.api_key_configured ? "" : " (sin API key)"}`;
}).catch(() => {});

document.body.dataset.lang = state.lang;
loadSamples();
connect();
