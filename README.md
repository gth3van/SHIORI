# 🌸 SHIORI — AI Waifu Companion

> Locally-run AI companion dengan voice interaction, semantic memory, web search, dan browser avatar.
> Kuudere. Sarkas. Suka tidur. Kayak kucing.

*Last updated: 2026-09-14*

---

## What is SHIORI?

SHIORI adalah AI companion yang jalan 100% lokal di PC kamu — ga ada cloud, ga ada subscription.
Lo bisa ngobrol via suara atau ketikan, dia jawab dengan suara anime Jepang, ingat siapa kamu, dan bisa searching internet kalau butuh info real-time.

- **Voice + text mode** — mic atau keyboard (`--mode text`)
- **Multilingual STT** — Indo, Inggris, Jepang via faster-whisper
- **Semantic memory** — ingat kamu lintas sesi, dicari by meaning (bukan keyword)
- **Auto web search** — detect sendiri kapan perlu search (Tavily + SearXNG fallback)
- **Local LLM** — Ollama + Qwen3:8b, fully private
- **Anime voice** — Edge-TTS NanamiNeural (Japanese)
- **Browser avatar** — buka di HP/tablet/layar lain lewat WiFi, ada loading screen

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
├── main.py                  # Asyncio orchestrator — semua sistem di sini
├── requirements.txt
├── ROADMAP.md
├── .env.example             # Copy ke .env, isi Tavily API key
│
├── brain/
│   └── llm_engine.py        # LLM + SHIORI persona (kuudere) + search dispatcher
│
├── voice/
│   ├── stt_listener.py      # Mic + faster-whisper STT
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
# Untuk soal teknis / engineering — lebih akurat tapi lebih lambat:
ollama pull qwen3:14b
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Web search (optional)

```bash
cp .env.example .env
# Isi TAVILY_API_KEY — free di https://app.tavily.com
```

### 5. Jalanin

```bash
python main.py                 # voice mode (default)
python main.py --mode text     # text mode
```

Buka **`http://localhost:8765`** — loading screen muncul, Ariu keluar.
Dari HP/tablet di WiFi yang sama: **`http://[IP-PC]:8765`**

---

## CLI Options

| Flag | Default | Keterangan |
|------|---------|------------|
| `--mode` | `voice` | `voice` (mic) atau `text` (keyboard) |
| `--volume` | `50` | Volume 0–100 |
| `--model` | `qwen3:8b` | Ollama model tag |
| `--think` | off | Aktifkan chain-of-thought (lebih lambat, lebih akurat) |
| `--no-tts` | — | Matikan audio output |
| `--no-avatar` | — | Skip avatar server |
| `--port` | `8765` | Port avatar server |
| `--no-memory` | — | Disable long-term memory |
| `--stt-model` | `base` | Whisper model size (`tiny`, `base`, `small`, `medium`) |
| `--stt-device` | `cpu` | `cpu` atau `cuda` |

**Contoh:**
```bash
python main.py --mode text --volume 30
python main.py --mode voice --model qwen3:14b --think   # engineering mode
python main.py --mode text --no-tts --no-avatar         # pure CLI mode
```

---

## Personality

SHIORI itu **kuudere** — kelihatan dingin dan cuek, tapi sebenernya perhatian (cuma ga mau kelihatan). Sarkas. Suka tidur. Ga suka direcokin tanpa alasan. Kayak kucing.

Ngomongnya campur-campur: Indo, Inggris, Jepang — tergantung mood. Dia punya opini sendiri, bisa nolak, bisa roasting kamu, tapi kalau bantu ya bantu beneran.

---

## Semantic Memory

ChromaDB vector search — dicari by **meaning**, bukan keyword exact.

```
Kamu:   "aku lagi ngerjain project tech"
Shiori: ingat → "User is developing an AI companion called SHIORI"
        (matched by meaning, phrasing-nya beda pun ketemu)
```

Disimpen lokal di `memory/chroma_db/` + JSON backup. Gitignored.

---

## Web Search

Auto-detect kapan perlu search. Trigger-nya luas — termasuk slang Indo:

```
"shiori tau Taskbar Heroes ga?"  → search otomatis
"apaan tuh Blue Archive?"        → search otomatis
"cuaca Jakarta sekarang?"        → search otomatis
```

Kalau mau paksa search: **"cariin / cek / search [topik]"**

Setup di `.env`:
```
TAVILY_API_KEY=tvly-...         # primary (free)
SEARXNG_URL=http://localhost:...  # fallback (optional, self-hosted)
```

---

## Avatar

Browser-based Live2D avatar via **oh-my-live2d** (Cubism Core bundled, no extra install).
Jalan di thread sendiri — ga ganggu voice loop.

```bash
python main.py
# → http://localhost:8765  (PC)
# → http://[IP]:8765       (HP/tablet/layar lain)
```

Loading screen nunjukin progress: library → model → WebSocket → ready.
Mulut Ariu gerak waktu Shiori ngomong (lip sync via requestAnimationFrame).

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

- 100% lokal — no OpenAI, no cloud LLM, no subscription
- Web search adalah satu-satunya optional cloud (Tavily free: 1000 req/bulan)
- Japanese voice by design — biar konsisten sama persona karakter
- `--think` OFF default buat real-time feel, ON buat soal teknis
- Semua data personal (memory, API keys) gitignored

---

*Built with love — 2026*
