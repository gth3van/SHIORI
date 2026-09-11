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

## ⏳ Phase 5 — Avatar (SHIORI gets a face)
> Goal: Live2D avatar that reacts and lip-syncs while speaking.
> Approach: VTube Studio WebSocket API — 100% Python, no C# needed.

**Setup needed:**
- VTube Studio (free on Steam)
- A Live2D model file (.vtube.model3.json) — buy on Booth.pm or use a free one

- [ ] `avatar/vtube_client.py` — WebSocket client for VTube Studio API
- [ ] Authenticate with VTube Studio plugin API (token-based)
- [ ] Lip sync — trigger mouth movement on TTS playback start/stop
- [ ] Emotion expressions mapped to reply tone (happy, thinking, surprised, idle)
- [ ] Idle animation loop when waiting for voice input
- [ ] Hotkey / parameter control for custom expressions

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
