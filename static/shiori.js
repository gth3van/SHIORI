"use strict";

const WS_URL       = `ws://${location.host}/ws`;
const MODEL_PATH   = "/static/model/ariu/ariu.model3.json";
const RECONNECT_MS = 3000;

let oml2d    = null;
let lipTimer = null;

// ── Loading screen ────────────────────────────────────────────────────────────
function stepActive(id) {
  const el = document.getElementById(id);
  if (el) el.className = "active";
}
function stepOk(id, label) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = "ok";
  if (label) el.lastChild.textContent = " " + label;
}
function stepFail(id, label) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = "fail";
  if (label) el.lastChild.textContent = " " + label;
  const errEl = document.getElementById("loader-error");
  if (errEl) { errEl.style.display = "block"; errEl.textContent = label; }
}
function hideLoader() {
  const l = document.getElementById("loader");
  if (!l) return;
  l.classList.add("fade-out");
  setTimeout(() => { if (l.parentNode) l.parentNode.removeChild(l); }, 900);
}

// ── Boot sequence ─────────────────────────────────────────────────────────────
(async function boot() {

  // Step 1 — Library
  stepActive("s-lib");
  await new Promise(r => setTimeout(r, 100));  // let browser paint first
  if (typeof OML2D === "undefined" || typeof OML2D.loadOml2d !== "function") {
    stepFail("s-lib", "Library failed to load");
    return;
  }
  stepOk("s-lib", "Library OK");

  // Step 2 — Model file reachable?
  stepActive("s-model");
  try {
    const res = await fetch(MODEL_PATH);
    if (!res.ok) throw new Error("HTTP " + res.status);
    stepOk("s-model", "Model file OK");
  } catch (e) {
    stepFail("s-model", "Model file error: " + e.message);
    return;
  }

  // Step 3 — WebSocket
  stepActive("s-ws");
  const wsOk = await new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), 3000);
    try {
      const ws = new WebSocket(WS_URL);
      ws.onopen  = () => { clearTimeout(timer); ws.close(); resolve(true); };
      ws.onerror = () => { clearTimeout(timer); resolve(false); };
    } catch { resolve(false); }
  });
  if (wsOk) {
    stepOk("s-ws", "WebSocket OK");
  } else {
    stepFail("s-ws", "WebSocket failed (Python not running?)");
    // Don't hard-stop — model can still show without WS
  }

  // Step 4 — Render model
  stepActive("s-ready");
  try {
    oml2d = await OML2D.loadOml2d({
      mobileDisplay: true,
      dockedPosition: "left",
      primaryColor: "rgba(0,0,0,0)",
      backgroundColor: "transparent",
      statusBar:  { display: false },
      menus:      { disable: true },
      tips:       { style: { display: "none" } },
      models: [{
        path: MODEL_PATH,
        scale: 0.1,
        position: [0, 0],
        stageStyle: {
          background: "transparent",
          width: window.innerWidth,
          height: window.innerHeight,
        },
      }],
    });

    // Force transparent on any injected canvas/stage elements
    document.querySelectorAll("canvas, #oml2d-stage, .oml2d-stage").forEach(el => {
      el.style.background = "transparent";
    });

    stepOk("s-ready", "Ariu is ready ✨");
    setTimeout(hideLoader, 800);
  } catch (e) {
    stepFail("s-ready", "Model render failed: " + e.message);
    return;
  }

  // Persistent WS for events
  connectWS();
})();

// ── Persistent WebSocket ──────────────────────────────────────────────────────
function connectWS() {
  let ws;
  try { ws = new WebSocket(WS_URL); } catch { setTimeout(connectWS, RECONNECT_MS); return; }
  ws.onclose = () => setTimeout(connectWS, RECONNECT_MS);
  ws.onerror = () => ws.close();
  ws.onmessage = (evt) => {
    let ev;
    try { ev = JSON.parse(evt.data); } catch { return; }
    switch (ev.type) {
      case "speaking": startLipFlap(ev.duration_ms || 0); oml2d?.model?.motion("Talk"); break;
      case "idle":     stopLipFlap(); oml2d?.model?.motion("Idle"); break;
      case "emotion":  oml2d?.model?.expression(ev.name); break;
      case "motion":   oml2d?.model?.motion(ev.name); break;
    }
  };
}

// ── Lip sync ──────────────────────────────────────────────────────────────────
function startLipFlap(duration_ms) {
  stopLipFlap();
  if (!oml2d) return;
  let open = false;
  lipTimer = setInterval(() => {
    open = !open;
    try {
      const core = oml2d.model?.internalModel?.coreModel;
      if (core) core.setParameterValueById("ParamMouthOpenY", open ? 0.8 : 0.1);
    } catch (_) {}
  }, 120);
  if (duration_ms > 0) setTimeout(stopLipFlap, duration_ms);
}
function stopLipFlap() {
  if (lipTimer) { clearInterval(lipTimer); lipTimer = null; }
  try {
    const core = oml2d?.model?.internalModel?.coreModel;
    if (core) core.setParameterValueById("ParamMouthOpenY", 0);
  } catch (_) {}
}
