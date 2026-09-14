/**
 * shiori.js
 * Live2D renderer + loading screen + WebSocket client.
 */
"use strict";

const WS_URL       = `ws://${location.host}/ws`;
const MODEL_PATH   = "/static/model/ariu/ariu.model3.json";
const RECONNECT_MS = 3000;

let oml2d    = null;
let lipTimer = null;

// ── Loading screen helpers ────────────────────────────────────────────────────
function stepActive(id) {
  const el = document.getElementById(id);
  if (el) { el.className = "active"; el.querySelector(".dot").style.animation = ""; }
}
function stepOk(id, label) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = "ok";
  if (label) el.childNodes[1].textContent = " " + label;
}
function stepFail(id, label) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = "fail";
  if (label) el.childNodes[1].textContent = " " + label;
  const errEl = document.getElementById("loader-error");
  if (errEl && label) { errEl.style.display = "block"; errEl.textContent = label; }
}
function hideLoader() {
  const loader = document.getElementById("loader");
  if (loader) {
    loader.classList.add("fade-out");
    setTimeout(() => loader.remove(), 900);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
(async function boot() {

  // Step 1 — Library
  stepActive("s-lib");
  if (typeof OML2D === "undefined" || typeof OML2D.loadOml2d !== "function") {
    stepFail("s-lib", "Library failed to load!");
    return;
  }
  stepOk("s-lib", "Library OK");

  // Step 2 — Model file
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
  await new Promise((resolve) => {
    const ws = new WebSocket(WS_URL);
    const timer = setTimeout(() => {
      stepFail("s-ws", "WebSocket timeout — is Python running?");
      resolve();
    }, 3000);
    ws.onopen = () => {
      clearTimeout(timer);
      stepOk("s-ws", "WebSocket connected");
      ws.close();
      resolve();
    };
    ws.onerror = () => {
      clearTimeout(timer);
      stepFail("s-ws", "WebSocket failed — Python not running");
      resolve();
    };
  });

  // Step 4 — Load model
  stepActive("s-ready");
  try {
    oml2d = await OML2D.loadOml2d({
      mobileDisplay: true,
      dockedPosition: "left",
      primaryColor: "rgba(0,0,0,0)",
      statusBar:  { display: false },
      menus:      { disable: true },
      tips:       { style: { display: "none" } },
      models: [{
        path: MODEL_PATH,
        scale: 0.1,
        position: [0, 0],
        stageStyle: { width: window.innerWidth, height: window.innerHeight },
      }],
    });
    stepOk("s-ready", "Ariu is ready ✨");
    setTimeout(hideLoader, 800);   // brief pause so user sees "ready"
  } catch (e) {
    stepFail("s-ready", "Model render failed: " + e.message);
    return;
  }

  // Persistent WebSocket for events
  connectWS();

})();

// ── WebSocket (persistent, auto-reconnect) ────────────────────────────────────
function connectWS() {
  const ws = new WebSocket(WS_URL);
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
