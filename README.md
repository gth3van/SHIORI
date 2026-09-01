# SHIORI 🌸 — AI Waifu Companion

> A real-time AI companion with voice interaction, long-term memory, and a Live2D avatar (coming soon).  
> Speaks with you, remembers you, and feels alive.

*Last updated: 2026-09-01*

---

## ✨ What is SHIORI?

SHIORI is a locally-run AI waifu companion that you talk to using your voice.  
She listens, thinks, and talks back — in real time, no cloud required.

- 🎙️ **Speaks to you** using a natural Japanese anime voice
- 👂 **Listens** to your microphone and transcribes speech in any language
- 🧠 **Remembers** things you tell her across sessions
- 💬 **Powered by a local LLM** (Ollama + Qwen3) — fully private, runs on your PC
- 🌐 **Multilingual** — English, Indonesian, Japanese

---

## 🏗️ Architecture

```
🎙️  Microphone
      │
      ▼
 STT Listener          faster-whisper (local, multilingual)
      │
      ▼
 Memory Engine         Recalls relevant facts about you
      │
      ▼
 LLM Brain             Ollama + Qwen3:14b (local, no API key)
      │
      ▼
 TTS Speaker           Edge-TTS → NanamiNeural (Japanese voice)
      │
      ▼
 🔊  Speaker output
```

---

## 📁 Project Structure

```
SHIORI/
├── main.py                  # Central asyncio orchestrator
├── requirements.txt         # Python dependencies
├── ROADMAP.md               # Feature roadmap & build checklist
│
├── brain/
│   └── llm_engine.py        # Ollama LLM client + SHIORI persona + Qwen3 think-strip
│
├── voice/
│   ├── stt_listener.py      # Microphone capture + faster-whisper STT
│   └── tts_speaker.py       # Edge-TTS synthesis + pygame playback
│
└── memory/
    └── memory_engine.py     # JSON-based long-term memory vault
```

---

## 🚀 Quick Start

### 1. Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- A working microphone

### 2. Pull the LLM model

```bash
ollama pull qwen3:14b
```

> **Recommended specs:** RTX GPU with 8GB+ VRAM. `qwen3:14b` fits entirely in 12GB VRAM.  
> For lower-spec machines, use `qwen3:4b` instead.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run SHIORI

```bash
python main.py
```

Speak into your microphone — SHIORI will listen, think, and reply!

---

## ⚙️ Options

```bash
python main.py --model qwen3:14b      # LLM model (default: qwen3:14b)
python main.py --think                # Enable Qwen3 thinking mode (slower, smarter)
python main.py --no-memory            # Disable long-term memory
python main.py --stt-model small      # Use a more accurate STT model
python main.py --stt-device cuda      # Run STT on GPU (faster)
```

---

## 🧠 Memory

SHIORI remembers facts you tell her across sessions.  
Her memory is stored locally in `memory/shiori_memory.json` (excluded from git — your data stays private).

**She will remember things like:**
- *"Aku suka kopi"* → she knows you like coffee
- *"My name is ..."* → she knows your name
- *"Aku lagi ngembangkan AI"* → she knows what you are working on

You can view and edit her memory vault directly — it is a plain JSON file.

---

## 🗺️ Roadmap

| Phase | Feature | Status |
|---|---|---|
| 1 | Core voice loop (STT → LLM → TTS) | ✅ Done |
| 2 | Long-term memory (JSON vault) | ✅ Done |
| 3 | Tool use — web search, timers, system control | ⏳ Planned |
| 4 | Smarter memory — ChromaDB vector search | ⏳ Planned |
| 5 | Live2D avatar via VTube Studio WebSocket | ⏳ Planned |
| 6 | Full JARVIS mode — agentic tasks, PC automation | ⏳ Planned |

See [`ROADMAP.md`](ROADMAP.md) for the full detailed checklist.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) |
| LLM | [Ollama](https://ollama.com) + [Qwen3](https://qwen.readthedocs.io) |
| TTS | [Edge-TTS](https://github.com/rany2/edge-tts) (NanamiNeural) |
| Audio playback | pygame |
| Memory | JSON vault (→ ChromaDB in Phase 4) |
| Avatar (planned) | VTube Studio WebSocket API |

---

## 📝 Notes

- SHIORI runs **100% locally** — no OpenAI API, no cloud, no subscriptions
- Thinking mode is **disabled by default** for real-time response feel — enable with `--think` for complex tasks
- The Japanese voice (NanamiNeural) is used for all languages by design
- Memory vault is **gitignored** — your personal data never leaves your machine

---

*Built with ❤️ — 2026*
