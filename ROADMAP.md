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
- [ ] `brain/llm_engine.py` — Set thinking_mode=False default + wire /no_think prefix
- [ ] `main.py` — Central asyncio orchestrator (STT → Brain → TTS loop)

**Model:** `qwen3:14b` on RTX 4070 12GB (fully GPU, no CPU offload)
**Thinking mode:** OFF by default (real-time waifu feel, low latency)

---

## ⏳ Phase 2 — Memory (SHIORI remembers you)
> Goal: SHIORI builds a personal knowledge vault about the user over time.
> Like Obsidian, but in her head.

- [ ] `memory/memory_engine.py` — JSON-based memory vault
  - [ ] `remember(fact)` — save a timestamped memory
  - [ ] `recall(query)` — keyword search across saved memories
  - [ ] `inject_into_prompt(query)` — inject relevant memories into LLM context
  - [ ] `forget(fact_id)` — delete a specific memory
- [ ] `memory/shiori_memory.json` — auto-created on first run (her "brain file")
- [ ] Wire memory into `main.py` (recall before LLM call, save after)
- [ ] SHIORI auto-extracts facts from conversation ("I hate spicy food" → saved)

---

## ⏳ Phase 3 — Tool Use (SHIORI can DO things)
> Goal: SHIORI can answer real questions and control basic things.
> "Hey SHIORI, what's the weather?" / "Set a 10 minute timer"

- [ ] `tools/` module folder
- [ ] `tools/web_search.py` — DuckDuckGo or SerpAPI search
- [ ] `tools/timer.py` — set/cancel timers with voice confirmation
- [ ] `tools/system.py` — volume control, open apps, basic PC control
- [ ] Tool dispatcher in `brain/llm_engine.py` (function calling via Qwen3)
- [ ] Dynamic thinking mode — ON for tool tasks, OFF for casual chat

---

## ⏳ Phase 4 — Smarter Memory (Upgrade)
> Goal: SHIORI finds memories by MEANING, not just keywords.
> "I'm cold" → she remembers "user lives somewhere cold"

- [ ] Replace JSON keyword search with ChromaDB vector database
- [ ] `memory/vector_store.py` — ChromaDB local embedding store
- [ ] Embed memories on save, semantic search on recall
- [ ] Keep JSON vault as human-readable backup/export

---

## ⏳ Phase 5 — Avatar (SHIORI gets a face)
> Goal: Live2D / VTube Studio avatar that reacts while speaking.

- [ ] `avatar/vtube_client.py` — WebSocket client for VTube Studio API
- [ ] Lip sync trigger on TTS playback start/stop
- [ ] Emotion expressions (happy, thinking, surprised) mapped to LLM tone
- [ ] Idle animation loop when waiting for input

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
