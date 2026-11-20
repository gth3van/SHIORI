"use strict";

const WS_URL       = `ws://${location.host}/ws`;
const MODEL_PATH   = "/static/model/ariu/ariu.model3.json";
const RECONNECT_MS = 3000;

let oml2d = null;

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
    oml2d = OML2D.loadOml2d({
      mobileDisplay: true,
      dockedPosition: "left",
      primaryColor: "rgba(0,0,0,0)",
      backgroundColor: "transparent",
      statusBar:  { display: false },
      menus:      { disable: true },
      tips:       { style: { display: "none" } },
      models: [{
        path: MODEL_PATH,
        scale: 0.22,
        position: [0, 80],
        stageStyle: {
          background: "transparent",
          width: Math.min(window.innerWidth, 500),
          height: window.innerHeight,
        },
      }],
    });
    await new Promise((resolve, reject) => {
      oml2d.onLoad((status) => {
        if (status === "success") resolve();
        if (status === "fail") reject(new Error("Live2D model or asset failed to load"));
      });
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
    const model = oml2d?.models.model;
    switch (ev.type) {
      case "speaking": startLipFlap(ev.duration_ms || 0); model?.motion("Talk"); break;
      case "idle":     stopLipFlap(); model?.motion("Idle"); break;
      case "emotion":  model?.expression(ev.name); break;
      case "motion":   model?.motion(ev.name); break;
    }
  };
}

// ── Lip sync ──────────────────────────────────────────────────────────────────
let _lipActive   = false;
let _mouthOpen   = 0;      // 0.0 – 1.0, driven by rAF loop
let _lipStopAt   = 0;      // performance.now() timestamp when to stop
let _rafId       = null;

// Possible parameter names used by different Live2D models
const MOUTH_PARAMS = ["ParamMouthOpenY", "PARAM_MOUTH_OPEN_Y", "ParamMouthOpen"];

function _setMouth(value) {
  const core = oml2d?.models.model?.internalModel?.coreModel;
  if (!core) return;
  for (const p of MOUTH_PARAMS) {
    try { core.setParameterValueById(p, value); } catch (_) {}
  }
}

function _lipLoop(ts) {
  if (!_lipActive) {
    _setMouth(0);
    _rafId = null;
    return;
  }
  if (_lipStopAt > 0 && ts >= _lipStopAt) {
    _lipActive = false;
    _setMouth(0);
    _rafId = null;
    return;
  }
  // Oscillate mouth open/closed at ~8 Hz
  _mouthOpen = (Math.sin(ts / 65) > 0) ? 0.8 : 0.05;
  _setMouth(_mouthOpen);
  _rafId = requestAnimationFrame(_lipLoop);
}

function startLipFlap(duration_ms) {
  _lipActive = true;
  _lipStopAt = duration_ms > 0 ? performance.now() + duration_ms : 0;
  if (!_rafId) _rafId = requestAnimationFrame(_lipLoop);
}

function stopLipFlap() {
  _lipActive = false;
  _lipStopAt = 0;
  _setMouth(0);
}
