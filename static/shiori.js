/**
 * shiori.js
 * Live2D controller using oh-my-live2d (all-in-one, no separate Cubism Core needed)
 * + WebSocket client for real-time Python -> browser events.
 *
 * Events from Python:
 *   { type: "speaking",  duration_ms: 2400 }
 *   { type: "idle" }
 *   { type: "emotion",   name: "happy" }
 *   { type: "motion",    name: "Tap@Body" }
 */

"use strict";

const WS_URL       = `ws://${location.host}/ws`;
const MODEL_PATH   = "/static/model/ariu/ariu.model3.json";
const RECONNECT_MS = 3000;

let oml2d     = null;   // oh-my-live2d instance
let lipTimer  = null;

// ── Boot oh-my-live2d ─────────────────────────────────────────────────────────
async function initLive2D() {
  setStatus("Loading model...");
  try {
    // OML2D is exposed globally by oh-my-live2d
    oml2d = await OML2D.loadOml2d({
      dockedPosition: "left",       // anchor model to left side
      mobileDisplay: true,          // show on mobile too
      primaryColor: "rgba(0,0,0,0)",

      // Disable all default UI chrome we don't want
      statusBar: { display: false },
      menus: { disable: true },
      tips: { style: { display: "none" } },

      models: [
        {
          path: MODEL_PATH,
          scale: 0.1,
          position: [0, 0],
          stageStyle: {
            width:  window.innerWidth,
            height: window.innerHeight,
          },
        },
      ],
    });

    setStatus("");
    console.log("[SHIORI] Model loaded via oh-my-live2d");
  } catch (e) {
    console.error("[SHIORI] Model load error:", e);
    setStatus("Model load failed — check console (F12)");
  }
}

// ── Lip sync ──────────────────────────────────────────────────────────────────
function startLipFlap(duration_ms) {
  stopLipFlap();
  if (!oml2d) return;
  let open = false;
  lipTimer = setInterval(() => {
    open = !open;
    try {
      // Access internal Live2D model for parameter control
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

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWS() {
  const ws = new WebSocket(WS_URL);

  ws.onopen  = () => { setStatus(""); console.log("[SHIORI] WS connected"); };
  ws.onclose = () => { setTimeout(connectWS, RECONNECT_MS); };
  ws.onerror = () => ws.close();

  ws.onmessage = (evt) => {
    let event;
    try { event = JSON.parse(evt.data); } catch { return; }

    switch (event.type) {
      case "speaking":
        startLipFlap(event.duration_ms || 0);
        oml2d?.model?.motion("Talk");
        break;
      case "idle":
        stopLipFlap();
        oml2d?.model?.motion("Idle");
        break;
      case "emotion":
        oml2d?.model?.expression(event.name);
        break;
      case "motion":
        oml2d?.model?.motion(event.name);
        break;
    }
  };
}

// ── Util ──────────────────────────────────────────────────────────────────────
function setStatus(msg) {
  const el = document.getElementById("status");
  if (el) el.textContent = msg;
}

// ── Boot ──────────────────────────────────────────────────────────────────────
initLive2D();
connectWS();
