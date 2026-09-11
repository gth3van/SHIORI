# SHIORI — Project Roadmap & Build Checklist

> This file lives in the repo so both you and the AI always know what's done,
> what's next, and where the project is heading.
> Update checkboxes as features are completed.

---

## ✅ Phase 1 — Core Voice Loop (MVP)
> Goal: Talk to SHIORI, she talks back. Real-time, personality-driven.

- [x] `voice/stt_listener.py` — Microphone capture + faster-whisper transcription
- [x] `voice/tts_speaker.py` — Edge-TTS synthesis + pygame playback (EN/JA/ID)
- [x] `brain/llm_engine.py` — Ollama async LLM client + SHIORI persona + Qwen3 think-strip
- [x] `brain/llm_engine.py` — thinking_mode=False default + /no_think prefix wired
- [x] `main.py` — Central asyncio orchestrator (STT → Brain → TTS loop)

**Model:** `qwen3:14b` on RTX 4070 12GB (fully GPU, no CPU offload)
**Thinking mode:** OFF by default (real-time waifu feel, low latency)

---

## ⏳ Phase 2 — Memory (SHIORI remembers you)
> Goal: SHIORI builds a personal knowledge vault about the user over time.
> Like Obsidian, but in her head.

- [x] `memory/memory_engine.py` — JSON-based memory vault
  - [x] `remember(fact)` — save a timestamped memory
  - [x] `recall(query)` — keyword search across saved memories
  - [x] `inject_into_prompt(query)` — inject relevant memories into LLM context
  - [x] `forget(fact_id)` — delete a specific memory
- [x] `memory/shiori_memory.json` — auto-created on first run (her "brain file")
- [x] Wire memory into `main.py` (recall before LLM call, save after)
- [ ] SHIORI auto-extracts facts from conversation ("I hate spicy food" → saved) ← basic version done, LLM-based extraction in Phase 4

---

## ✅ Phase 3 — Tool Use (SHIORI can DO things)
> Goal: SHIORI can answer real questions and control basic things.
> "Hey SHIORI, what's the weather?" / "Set a 10 minute timer"

- [x] `tools/` module folder
- [x] `tools/web_search.py` — Tavily AI Search (primary) + SearXNG self-hosted (fallback)
- [x] Tool dispatcher in `brain/llm_engine.py` — auto-detects search intent (EN + ID)
- [x] Dynamic thinking mode — ON automatically for tool/search tasks
- [ ] `tools/timer.py` — set/cancel timers with voice confirmation
- [ ] `tools/system.py` — volume control, open apps, basic PC control

---

## ✅ Phase 4 — Smarter Memory (Upgrade)
> Goal: SHIORI finds memories by MEANING, not just keywords.
> "I'm cold" → she remembers "user lives somewhere cold"

- [x] Replace JSON keyword search with ChromaDB vector database
- [x] `memory/vector_store.py` — ChromaDB local embedding store (all-MiniLM-L6-v2)
- [x] Embed memories on save, semantic search on recall (cosine similarity)
- [x] Keep JSON vault as human-readable backup/export (auto-synced)
- [x] Auto-migrate existing JSON memories into ChromaDB on first run
- [x] Graceful fallback to keyword search if ChromaDB not available

---

## 🔄 Phase 5 — 3D Avatar (VRM + Three.js) [Infrastructure ✅, Renderer pending]
> Goal: SHIORI has a 3D VRChat-compatible avatar viewable in any browser.
> Accessible from any device on the same WiFi network.

**Infrastructure ✅ already built:**
- [x] `server/app.py` — FastAPI server, serves HTML + WebSocket on port 8080
- [x] `server/ws_bridge.py` — async broadcast helper (Python → browser)
- [x] `main.py` — starts avatar server on boot, fires speaking/idle WS events
- [x] LAN accessible — open `http://[PC-IP]:8080` on phone/tablet/second screen

**Renderer swap (waiting for model purchase):**
- [ ] Swap `static/shiori.js` Pixi.js/Live2D → Three.js + `@pixiv/three-vrm`
- [ ] VRM BlendShape lip sync (mouth shapes: A, O, U)
- [ ] VRM SpringBone physics (hair + clothing react naturally)
- [ ] Drop `.vrm` model into `static/model/` to activate

**Notes:**
- Target: `.vrm` format (VRChat-compatible, works in browser via CDN — no Node.js)
- If model comes as `.unitypackage` → export via Unity + UniVRM plugin first
- WebSocket server requires zero changes when swapping the renderer


**Architecture:**
```
SHIORI (Python) ──WebSocket──▶ VTube Studio ──▶ Live2D Model
```

---

## ⏳ Phase 6 — Full JARVIS Mode
> Goal: SHIORI becomes a full AI assistant, not just a companion.

- [ ] Long-horizon agentic tasks (multi-step reasoning)
- [ ] File management — read/write/summarize documents
- [ ] Code assistance — explain, debug, write code on request
- [ ] Email / calendar integration
- [ ] Thinking mode ON automatically for complex tasks
- [ ] Upgrade to `qwen3.8:27b` or larger when hardware allows

---

## Design Decisions Log

| Date | Decision | Reason |
|---|---|---|
| 2026-09-01 | Model: `qwen3:14b` | Fits fully in RTX 4070 12GB VRAM |
| 2026-09-01 | Thinking mode OFF by default | Low latency > deep reasoning for waifu feel |
| 2026-09-01 | Memory: Option A (JSON vault) | Human-readable, editable like Obsidian notes |
| 2026-09-01 | TTS: Edge-TTS + pygame | Free, multilingual, no API key needed |
| 2026-09-01 | STT: faster-whisper base.en | Fast local transcription, no cloud needed |
