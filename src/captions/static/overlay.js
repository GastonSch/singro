const params = new URLSearchParams(location.search);
const session = params.get("session") || "";
const lang = params.get("lang") || "translation";
document.body.dataset.lang = lang;

const originalEl = document.getElementById("original");
const translationEl = document.getElementById("translation");
const tagEl = document.getElementById("tag");

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "sessions") {
      const match = msg.sessions.find((s) => s.id === session);
      tagEl.textContent = match ? match.name : session;
      return;
    }
    if (msg.session !== session) return;
    if (msg.type === "caption") {
      if (msg.lane === "original") originalEl.textContent = msg.text;
      else translationEl.textContent = msg.text;
    }
    if (msg.type === "block") {
      if (msg.original) originalEl.textContent = msg.original;
      if (msg.translation) translationEl.textContent = msg.translation;
    }
  };
  ws.onclose = () => setTimeout(connect, 1500);
}

connect();
