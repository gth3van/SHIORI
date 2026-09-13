/**
 * shiori.js
 * Live2D controller + WebSocket client for SHIORI avatar.
 *
 * Events received from Python:
 *   { type: "speaking",  duration_ms: 2400 }  SHIORI started talking
 *   { type: "idle" }                           SHIORI finished talking
 *   { type: "emotion",   name: "happy" }       Set expression
 *   { type: "motion",    name: "wave" }        Trigger motion group
 *   { type: "load_model", path: "haru/haru_greeter_t03.model3.json" }
 */

"use strict";

// ── Config ───────────────────────────────────────────────────────────────────
const WS_URL        = `ws://${location.host}/ws`;
const DEFAULT_MODEL = "/static/model/ariu/ariu.model3.json";
const RECONNECT_MS  = 3000;

// ── State ────────────────────────────────────────────────────────────────────
let app    = null;   // Pixi.Application
let model  = null;   // Live2DModel
let ws     = null;
let lipInterval = null;

// ── Pixi init ────────────────────────────────────────────────────────────────
async function initPixi() {
  app = new PIXI.Application({
    width:            window.innerWidth,
    height:           window.innerHeight,
    backgroundAlpha:  0,          // transparent — looks good on any bg
    antialias:        true,
    resolution:       window.devicePixelRatio || 1,
  });
  document.body.appendChild(app.view);

  window.addEventListener("resize", () => {
    app.renderer.resize(window.innerWidth, window.innerHeight);
    if (model) fitModel();
  });

  setStatus("Pixi ready. Waiting for model...");
  await tryLoadModel(DEFAULT_MODEL);
}

// ── Model loading ─────────────────────────────────────────────────────────────
async function tryLoadModel(path) {
  try {
    const live2dModel = await PIXI.live2d.Live2DModel.from(path, {
      autoInteract: false,
    });
    if (model) {
      app.stage.removeChild(model);
      model.destroy();
    }
    model = live2dModel;
    app.stage.addChild(model);
    fitModel();
    setStatus("");   // hide status once model is loaded
    console.log("[SHIORI] Model loaded:", path);
  } catch (e) {
    console.warn("[SHIORI] Could not load model:", e);
    setStatus("Model not found — check static/model/ariu/");
  }
}

function fitModel() {
  if (!model) return;
  // Scale to fill ~90% of the shorter screen dimension
  const scale = Math.min(
    window.innerWidth  / model.internalModel.originalWidth,
    window.innerHeight / model.internalModel.originalHeight
  ) * 0.9;
  model.scale.set(scale);
  // Center on screen
  model.x = (window.innerWidth  - model.internalModel.originalWidth  * scale) / 2;
  model.y = (window.innerHeight - model.internalModel.originalHeight * scale) / 2;
}

// ── Lip sync ──────────────────────────────────────────────────────────────────
function startLipFlap(duration_ms) {
  if (!model) return;
  stopLipFlap();
  let open = false;
  lipInterval = setInterval(() => {
    open = !open;
    try {
      model.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", open ? 0.8 : 0.1);
    } catch (_) {}
  }, 120);
  // Auto stop after duration
  if (duration_ms > 0) setTimeout(stopLipFlap, duration_ms);
}

function stopLipFlap() {
  if (lipInterval) {
    clearInterval(lipInterval);
    lipInterval = null;
  }
  try {
    model?.internalModel.coreModel.setParameterValueById("ParamMouthOpenY", 0);
  } catch (_) {}
}

// ── Expression / Motion ───────────────────────────────────────────────────────
function setEmotion(name) {
  if (!model) return;
  try { model.expression(name); } catch (e) { console.warn("Expression not found:", name); }
}

function triggerMotion(name) {
  if (!model) return;
  try { model.motion(name); } catch (e) { console.warn("Motion not found:", name); }
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWS() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setStatus("Connected to SHIORI ✅");
    console.log("[SHIORI] WS connected.");
  };

  ws.onmessage = (evt) => {
    let event;
    try { event = JSON.parse(evt.data); } catch { return; }

    switch (event.type) {
      case "speaking":
        triggerMotion("Talk");
        startLipFlap(event.duration_ms || 0);
        break;
      case "idle":
        stopLipFlap();
        triggerMotion("Idle");
        break;
      case "emotion":
        setEmotion(event.name);
        break;
      case "motion":
        triggerMotion(event.name);
        break;
      case "load_model":
        tryLoadModel("/static/model/" + event.path);
        break;
      default:
        console.log("[SHIORI] Unknown event:", event);
    }
  };

  ws.onclose = () => {
    setStatus("Disconnected. Reconnecting...");
    setTimeout(connectWS, RECONNECT_MS);
  };

  ws.onerror = () => ws.close();
}

// ── Util ──────────────────────────────────────────────────────────────────────
function setStatus(msg) {
  const el = document.getElementById("status");
  if (el) el.textContent = msg;
}

// ── Boot ──────────────────────────────────────────────────────────────────────
initPixi();
connectWS();
