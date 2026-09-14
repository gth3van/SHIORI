# 🌸 SHIORI — AI Waifu Companion

> Locally-run AI companion with voice interaction, semantic memory, web search, and a browser-based avatar.
> Kuudere. Sarcastic. Loves to sleep. Basically a cat.

*Last updated: 2026-09-14*

---

## What is SHIORI?

SHIORI is an AI companion that runs 100% locally on your PC — no cloud, no subscriptions.
You can talk to her via voice or text, she responds with a Japanese anime voice, remembers who you are, and can search the internet for real-time information when needed.

- **Voice + text mode** — speak via mic or type (`--mode text`)
- **Multilingual STT** — English, Indonesian, Japanese via faster-whisper
- **Semantic memory** — remembers you across sessions, queried by meaning (not keywords)
- **Auto web search** — detects when it needs to search the web (Tavily + SearXNG fallback)
- **Local LLM** — Ollama + Qwen3:8b, fully private
- **Anime voice** — Edge-TTS NanamiNeural (Japanese)
- **Browser avatar** — open on your phone/tablet/second screen over WiFi, with a loading screen

---

## Architecture

```
Mic / Keyboard
      |
      v
 STT Listener     faster-whisper (local, multilingual)
      |
      v
 Memory Engine    ChromaDB vector search — recall by meaning
      |
      v
 LLM Brain        Ollama + Qwen3:8b (local)
      |  <-> auto web search (Tavily → SearXNG)
      v
 TTS Speaker      Edge-TTS → NanamiNeural
      |
      v
 Audio + WebSocket → Browser avatar (oh-my-live2d, Live2D .moc3)
```

---

## Project Structure

```
SHIORI/
├── main.py                  # Asyncio orchestrator — core system
├── requirements.txt
├── ROADMAP.md
├── .env.example             # Copy to .env, add Tavily API key
│
├── brain/
│   └── llm_engine.py        # LLM + SHIORI persona (kuudere) + search dispatcher
│
├── voice/
│   ├── stt_listener.py      # Mic capture + faster-whisper STT
│   └── tts_speaker.py       # Edge-TTS + pygame playback + volume control
│
├── memory/
│   ├── memory_engine.py     # ChromaDB primary, JSON fallback
│   └── vector_store.py      # ChromaDB wrapper
│
├── tools/
│   └── web_search.py        # Tavily + SearXNG fallback
│
└── server/
    ├── app.py               # FastAPI avatar server (default port 8765)
    └── ws_bridge.py         # WebSocket broadcast → browser

static/
├── shiori.html              # Avatar viewer + loading screen
├── shiori.js                # oh-my-live2d controller + WebSocket client
├── oh-my-live2d.min.js      # Bundled renderer (Cubism Core included)
└── model/                   # .moc3 model files (gitignored)
```

---

## Quick Start

### 1. Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running

### 2. Pull LLM model

```bash
ollama pull qwen3:8b
# For technical/engineering questions — more accurate but slower:
ollama pull qwen3:14b
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Web search (optional)

```bash
cp .env.example .env
# Add TAVILY_API_KEY — free at https://app.tavily.com
```

### 5. Run SHIORI

```bash
python main.py                 # voice mode (default)
python main.py --mode text     # text mode
```

Open **`http://localhost:8765`** — a loading screen will appear, followed by Ariu.
From a phone/tablet on the same WiFi: **`http://[YOUR-PC-IP]:8765`**

---

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `voice` | `voice` (mic) or `text` (keyboard) |
| `--volume` | `50` | Volume 0–100 |
| `--model` | `qwen3:8b` | Ollama model tag |
| `--think` | off | Enable chain-of-thought (slower, more accurate) |
| `--no-tts` | — | Disable audio output |
| `--no-avatar` | — | Skip avatar server |
| `--port` | `8765` | Avatar server port |
| `--no-memory` | — | Disable long-term memory |
| `--stt-model` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`) |
| `--stt-device` | `cpu` | `cpu` or `cuda` |

**Examples:**
```bash
python main.py --mode text --volume 30
python main.py --mode voice --model qwen3:14b --think   # engineering mode
python main.py --mode text --no-tts --no-avatar         # pure CLI mode
```

---

## Personality

SHIORI is a **kuudere** — she seems cold and aloof, but is actually caring (she just doesn't want to show it). Sarcastic. Loves to sleep. Gets annoyed if bothered without a good reason. Just like a cat.

She code-switches naturally between Indonesian, English, and Japanese depending on her mood. She has her own opinions, can refuse to do things, might roast you, but if she decides to help, she really helps.

---

## Semantic Memory

Uses ChromaDB vector search — queries by **meaning**, not exact keywords.

```
You:    "I'm working on a tech project"
Shiori: remembers → "User is developing an AI companion called SHIORI"
        (matched by meaning, even if phrased differently)
```

Stored locally in `memory/chroma_db/` + JSON backup. Gitignored.

---

## Web Search

Auto-detects when a web search is needed. Triggers are broad and include casual slang (EN/ID):

```
"does shiori know about Taskbar Heroes?"  → auto search
"what is Blue Archive?"                   → auto search
"weather in Jakarta right now?"           → auto search
```

To force a search: **"search / look up [topic]"**

Setup in `.env`:
```
TAVILY_API_KEY=tvly-...           # primary (free)
SEARXNG_URL=http://localhost:...  # fallback (optional, self-hosted)
```

---

## Avatar

Browser-based Live2D avatar via **oh-my-live2d** (Cubism Core bundled, no extra installation).
Runs in its own daemon thread — doesn't block the voice loop.

```bash
python main.py
# → http://localhost:8765  (PC)
# → http://[IP]:8765       (Phone/tablet/second screen)
```

A loading screen shows the boot progress: library → model → WebSocket → ready.
Ariu's mouth moves when Shiori speaks (frame-accurate lip sync via requestAnimationFrame).

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Core voice loop (STT → LLM → TTS) | ✅ Done |
| 2 | Long-term memory (JSON) | ✅ Done |
| 3 | Web search + text mode | ✅ Done |
| 4 | Semantic memory (ChromaDB) | ✅ Done |
| 5 | Browser avatar (Live2D, WebSocket, loading screen) | ✅ Done |
| 5.5 | RVC voice conversion | 🔄 In progress |
| 6 | Full JARVIS mode — agentic tasks, PC automation | Planned |
| 7 | 3D VRM avatar (Three.js + three-vrm) | Planned |

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.10+ |
| STT | faster-whisper (local) |
| LLM | Ollama + Qwen3:8b (local) |
| TTS | Edge-TTS NanamiNeural |
| Voice conversion | RVC (in progress) |
| Memory | ChromaDB + JSON backup |
| Web search | Tavily AI + SearXNG fallback |
| Avatar server | FastAPI + WebSocket (daemon thread) |
| Avatar renderer | oh-my-live2d (Cubism 4, all-in-one) |
| Audio | pygame |

---

## Notes

- 100% local — no OpenAI, no cloud LLMs, no subscriptions.
- Web search is the only optional cloud service (Tavily free tier: 1000 req/month).
- Japanese voice is used for all languages by design (consistent with the anime persona).
- `--think` is OFF by default for real-time conversation speed, turn it ON for technical questions.
- All personal data (memory, API keys) is gitignored.

---

*Built with love — 2026*
