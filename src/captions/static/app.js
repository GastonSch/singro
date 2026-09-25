const state = {
  sessions: [],
  selected: null,
  data: {},
  lang: "both",
  videoType: null,
  videoSrc: null,
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
  headState: document.getElementById("head-state"),
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
  video: document.getElementById("video"),
  videoFrame: document.getElementById("video-frame"),
  videoFallback: document.getElementById("video-fallback"),
  videoTitle: document.getElementById("video-title"),
  videoSub: document.getElementById("video-sub"),
  run: document.getElementById("run"),
};

function ensure(id) {
  if (!state.data[id]) state.data[id] = { liveOriginal: "", liveTranslation: "", blocks: [], sourceLanguage: null, stats: {} };
  return state.data[id];
}
function current() {
  return state.sessions.find((s) => s.id === state.selected) || null;
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
    setVideo();
    renderStats();
    renderRunButton();
    return;
  }
  if (msg.type === "status") {
    const session = state.sessions.find((s) => s.id === msg.session);
    if (session) { session.state = msg.state; session.stats = msg.stats; }
    ensure(msg.session).stats = msg.stats;
    renderTabs();
    if (msg.session === state.selected) { renderStats(); renderRunButton(); }
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
    if (msg.session === state.selected) els.statState.textContent = "error";
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
  setVideo();
  renderRunButton();
}

function embedUrl(url, autoplay) {
  const m = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|live\/|embed\/))([\w-]{6,})/);
  const base = m ? `https://www.youtube.com/embed/${m[1]}` : url;
  const params = new URLSearchParams({ rel: "0", autoplay: autoplay ? "1" : "0" });
  return `${base}?${params.toString()}`;
}

function startMedia() {
  const session = current();
  if (!session) return;
  if (state.videoType === "video") {
    try { els.video.currentTime = 0; } catch { /* ignore */ }
    els.video.play().catch(() => {});
  } else if (state.videoType === "iframe" && session.video) {
    els.videoFrame.src = `${embedUrl(session.video, true)}&_=${Date.now()}`;
  }
}

function setVideo() {
  const session = current();
  const url = session?.video || "";
  els.videoFallback.style.display = url ? "none" : "block";
  els.videoTitle.textContent = session ? session.name : "—";
  els.videoSub.textContent = session ? `${session.source_language || "auto"} → ${session.target_language}` : "—";

  if (!url) {
    els.video.pause();
    els.video.hidden = true;
    els.videoFrame.hidden = true;
    els.video.removeAttribute("src");
    try { els.video.load(); } catch { /* ignore */ }
    state.videoType = null;
    state.videoSrc = null;
    return;
  }

  if (/youtube\.com|youtu\.be/.test(url)) {
    els.video.pause();
    els.video.hidden = true;
    els.videoFrame.hidden = false;
    const key = "yt:" + url;
    if (state.videoSrc !== key) { els.videoFrame.src = embedUrl(url, false); state.videoSrc = key; }
    state.videoType = "iframe";
  } else {
    els.videoFrame.hidden = true;
    els.video.hidden = false;
    if (state.videoSrc !== url) {
      els.video.pause();
      els.video.src = url;
      els.video.poster = url.replace(/\.mp4(\?.*)?$/i, ".jpg");
      state.videoSrc = url;
    }
    state.videoType = "video";
  }
}

function renderRunButton() {
  const session = current();
  const running = session && ["running", "starting"].includes(session.state);
  els.run.disabled = !session;
  els.run.textContent = running ? "■  Detener" : "▶  Ejecutar";
  els.run.classList.toggle("playing", !!running);
  els.headState.textContent = session?.state ?? "—";
  els.headState.className = "pill " + (session?.state ?? "");
}

async function toggleRun() {
  const session = current();
  if (!session) return;
  const running = ["running", "starting"].includes(session.state);
  if (running) {
    els.video.pause();
    await fetch(`/api/sessions/${encodeURIComponent(session.id)}/stop`, { method: "POST" });
  } else {
    startMedia();  // dentro del gesto del click, para que el navegador permita autoplay
    await fetch(`/api/sessions/${encodeURIComponent(session.id)}/start`, { method: "POST" });
  }
}

function blockNode(block) {
  const node = document.createElement("div");
  node.className = "block";
  node.innerHTML = `<div class="original">${escapeHtml(block.original)}</div><div class="translation">${escapeHtml(block.translation)}</div>`;
  return node;
}

function rebuildHistory() {
  els.history.innerHTML = "";
  const data = state.selected ? state.data[state.selected] : null;
  if (data) for (const block of data.blocks.slice(-200)) els.history.appendChild(blockNode(block));
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
  const session = current();
  const data = state.selected ? ensure(state.selected) : null;
  const stats = session?.stats ?? data?.stats ?? {};
  els.latency.textContent = stats.latency_ms != null ? `${Math.round(stats.latency_ms)} ms` : "–";
  els.segments.textContent = stats.segments ?? 0;
  els.errors.textContent = stats.errors ?? 0;
  els.statState.textContent = session?.state ?? "–";
  const base = state.selected ? `/api/sessions/${encodeURIComponent(state.selected)}/transcript` : "#";
  els.exportSrt.href = `${base}?format=srt&lang=${state.lang}`;
  els.exportVtt.href = `${base}?format=vtt&lang=${state.lang}`;
  els.exportTxt.href = `${base}?format=txt&lang=${state.lang}`;
  els.overlayLink.href = state.selected ? `/overlay?session=${encodeURIComponent(state.selected)}&lang=${state.lang}` : "#";
}

function cycleLang() {
  state.lang = state.lang === "both" ? "translation" : state.lang === "translation" ? "original" : "both";
  els.langToggle.textContent = { both: "ES + original", translation: "Solo ES", original: "Solo original" }[state.lang];
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

els.run.onclick = toggleRun;
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
    video: document.getElementById("f-video").value.trim(),
    source_language: document.getElementById("f-src").value || null,
    target_language: document.getElementById("f-target").value,
  };
  const response = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.ok) { els.dialog.close(); els.form.reset(); }
  else alert(`No se pudo crear la sesión: ${await response.text()}`);
};

fetch("/api/health").then((r) => r.json()).then((h) => {
  els.engine.textContent = `${h.engine}${h.api_key_configured ? "" : " (sin API key)"}`;
}).catch(() => {});

async function bootstrapSessions() {
  try {
    const response = await fetch("/api/sessions");
    if (!response.ok) return;
    const sessions = await response.json();
    state.sessions = sessions;
    for (const session of sessions) ensure(session.id);
    if (!state.selected || !sessions.find((s) => s.id === state.selected)) {
      state.selected = sessions[0]?.id ?? null;
    }
    renderTabs();
    rebuildHistory();
    setVideo();
    renderStats();
    renderRunButton();
  } catch { /* ignore */ }
}

document.body.dataset.lang = state.lang;
loadSamples();
bootstrapSessions();
connect();
