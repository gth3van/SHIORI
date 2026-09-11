# 🌸SHIORI - AI Waifu Companion🌸

> A real-time AI companion with voice interaction, web search, semantic memory, and a 3D avatar (coming soon).
> Speaks with you, remembers you, and feels alive.

*Last updated: 2026-09-12*

---

## What is SHIORI?

SHIORI is a locally-run AI waifu companion that you talk to using your voice -- or by typing.
She listens, thinks, searches the web when needed, and talks back -- in real time, no cloud required.

- **Voice + text input** -- speak via mic or type (`--mode text`)
- **Multilingual STT** -- English, Indonesian, Japanese via faster-whisper
- **Semantic memory** -- remembers you across sessions using ChromaDB vector search
- **Live web search** -- auto-detects when to search (Tavily AI + SearXNG fallback)
- **Local LLM** -- Ollama + Qwen3:14b, fully private, no API key needed
- **Japanese anime voice** -- Edge-TTS NanamiNeural, always
- **Browser avatar server** -- open on phone, tablet, or second screen over WiFi

---

## Architecture

```
Mic / Keyboard
      |
      v
 STT Listener          faster-whisper (local, multilingual)
      |
      v
 Memory Engine         ChromaDB vector search -- recalls by MEANING not keywords
      |
      v
 LLM Brain             Ollama + Qwen3:14b (local, no API key)
      |  <-> auto web search if needed (Tavily -> SearXNG fallback)
      v
 TTS Speaker           Edge-TTS -> NanamiNeural (Japanese voice)
      |
      v
 Speaker output + WebSocket -> Browser avatar (Pixi.js / Three.js)
```

---

## Project Structure

```
SHIORI/
├── main.py                  # Central asyncio orchestrator
├── requirements.txt         # Python dependencies
├── ROADMAP.md               # Feature roadmap & build checklist
├── .env.example             # API key template (copy to .env)
│
├── brain/
│   └── llm_engine.py        # Ollama LLM + SHIORI persona + tool dispatcher
│
├── voice/
│   ├── stt_listener.py      # Mic capture + faster-whisper STT
│   └── tts_speaker.py       # Edge-TTS synthesis + pygame playback
│
├── memory/
│   ├── memory_engine.py     # Semantic memory (ChromaDB primary, JSON fallback)
│   └── vector_store.py      # ChromaDB vector store wrapper
│
├── tools/
│   └── web_search.py        # Tavily AI search + SearXNG fallback
│
└── server/
    ├── app.py               # FastAPI avatar server (port 8080)
    └── ws_bridge.py         # WebSocket broadcast (Python -> browser)

static/
├── shiori.html              # Avatar viewer page
├── shiori.js                # Pixi.js controller + WebSocket client
└── model/                   # Drop your .vrm or .moc3 model here (gitignored)
```

---

## Quick Start

### 1. Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- A working microphone (optional -- text mode works without one)

### 2. Pull the LLM model

```bash
ollama pull qwen3:14b
```

> **Recommended specs:** RTX GPU with 8GB+ VRAM. `qwen3:14b` fits in 12GB VRAM.
> For lower-spec machines, use `qwen3:4b` instead.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up web search (optional)

```bash
cp .env.example .env
# Edit .env and add your Tavily API key (free at https://app.tavily.com)
```

### 5. Run SHIORI

```bash
python main.py                       # voice mode (default)
python main.py --mode text           # type instead of speaking
python main.py --mode text --no-tts  # silent text mode
```

Then open **http://localhost:8080** in any browser for the avatar viewer.
From phone/tablet on the same WiFi: **http://[YOUR-PC-IP]:8080**

---

## CLI Options

```bash
python main.py --mode text        # keyboard input instead of mic
python main.py --no-tts           # disable audio output
python main.py --no-avatar        # skip avatar web server
python main.py --port 9090        # custom avatar server port
python main.py --think            # enable Qwen3 thinking mode (smarter, slower)
python main.py --no-memory        # disable long-term memory
python main.py --model qwen3:4b   # use a lighter LLM model
python main.py --stt-model small  # more accurate STT
python main.py --stt-device cuda  # run STT on GPU
```

---

## Semantic Memory (Phase 4)

SHIORI remembers facts across sessions using **ChromaDB vector embeddings**.
Memory is searched by *meaning*, not just keywords -- so she understands context
even when you phrase things differently.

```
You:    "aku lagi ngerjain project tech"
SHIORI: remembers -> "User is developing an AI companion called SHIORI"
        (matched by meaning, not exact keywords)
```

Memory stored locally in `memory/chroma_db/` + JSON backup in `memory/shiori_memory.json`.
Both are gitignored. Your data never leaves your machine.

---

## Web Search (Phase 3)

SHIORI auto-detects when she needs real-world information and searches the web:

```
You:    "Shiori, cuaca Jakarta hari ini?"
SHIORI: -> detects search intent -> Tavily search -> answers with live data
```

**Triggers (EN + ID):** search, find, what is, who is, latest, today,
cari, apa itu, siapa, terbaru, berita, cuaca, harga, ...

Set up in `.env`:
```
TAVILY_API_KEY=tvly-your-key-here   # primary (free at app.tavily.com)
SEARXNG_URL=http://localhost:8080   # fallback (self-hosted, optional)
```

---

## Avatar (Phase 5 -- In Progress)

SHIORI serves a browser-based avatar viewer over your local network.
Any device on the same WiFi can open it.

```
python main.py
# -> open http://[PC-IP]:8080 on phone, tablet, or second screen
```

**Avatar setup:**
1. Get a `.vrm` (VRChat-compatible) or `.moc3` (Live2D) model from [Booth.pm](https://booth.pm)
2. Drop it into `static/model/`
3. Refresh the browser -- avatar animates when SHIORI speaks

> Currently using Pixi.js + pixi-live2d-display.
> Switching to Three.js + `@pixiv/three-vrm` for 3D VRM support once model is ready.

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Core voice loop (STT -> LLM -> TTS) | Done |
| 2 | Long-term memory (JSON vault) | Done |
| 3 | Web search (Tavily + SearXNG), text mode | Done |
| 4 | Semantic memory -- ChromaDB vector search | Done |
| 5 | Browser avatar server (FastAPI + WebSocket + Pixi.js) | Server done, model pending |
| 6 | Full JARVIS mode -- agentic tasks, PC automation | Planned |

See [ROADMAP.md](ROADMAP.md) for the full detailed checklist.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (local, multilingual) |
| LLM | [Ollama](https://ollama.com) + [Qwen3:14b](https://qwen.readthedocs.io) (local) |
| TTS | [Edge-TTS](https://github.com/rany2/edge-tts) -- NanamiNeural (Japanese) |
| Memory | [ChromaDB](https://www.trychroma.com) vector search + JSON backup |
| Web search | [Tavily AI](https://tavily.com) + [SearXNG](https://searxng.github.io/searxng/) fallback |
| Avatar server | [FastAPI](https://fastapi.tiangolo.com) + WebSocket |
| Avatar renderer | Pixi.js + pixi-live2d-display -> Three.js + three-vrm (pending) |
| Audio playback | pygame |

---

## Notes

- Runs **100% locally** -- no OpenAI API, no subscriptions required
- Web search is the only optional cloud service (Tavily free tier: 1000 req/month)
- Japanese voice (NanamiNeural) is used for all languages by design
- Thinking mode OFF by default for real-time feel -- use `--think` for harder questions
- All personal data (memory, API keys) is gitignored and stays on your machine

---

*Built with love -- 2026*
