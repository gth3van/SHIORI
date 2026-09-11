"""
main.py
───────
SHIORI — Central asyncio orchestrator.

Pipeline (one loop iteration):
  1. Input — voice (STT mic) or text (keyboard) depending on --mode
  2. MemoryEngine injects relevant facts into the LLM context
  3. LLMEngine generates SHIORI reply (web search auto-triggered if needed)
  4. MemoryEngine auto-extracts and saves any new facts from the exchange
  5. TTSSpeaker synthesises and plays the reply (skip with --no-tts)
  6. Avatar server broadcasts events to browser (Pixi.js Live2D)

Run:
    python main.py                           # voice mode + avatar server
    python main.py --mode text               # text mode — type instead of speak
    python main.py --mode text --no-tts      # text-only, no audio
    python main.py --no-avatar               # skip avatar server
    python main.py --port 8080               # custom avatar server port

Open browser at http://localhost:8080 (or your LAN IP from another device).

Dependencies:
    pip install faster-whisper sounddevice numpy edge-tts pygame ollama
    pip install fastapi uvicorn websockets
"""

from __future__ import annotations

import asyncio
import argparse
import socket
import sys
from pathlib import Path

from brain.llm_engine import LLMEngine, SHIORI_SYSTEM_PROMPT
from memory.memory_engine import MemoryEngine
from voice.tts_speaker import TTSSpeaker


# ---------------------------------------------------------------------------
# Avatar server helpers
# ---------------------------------------------------------------------------

def _get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "localhost"


async def _start_avatar_server(port: int) -> None:
    """Start the FastAPI/uvicorn avatar server as a background asyncio task."""
    try:
        import uvicorn
        from server.app import app
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=port,
            log_level="warning",   # suppress uvicorn access logs
        )
        server = uvicorn.Server(config)
        await server.serve()
    except ImportError:
        print("[Avatar] uvicorn/fastapi not installed — avatar server disabled.")
    except Exception as e:
        print(f"[Avatar] Server error: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_facts(user_input: str, reply: str) -> list[str]:
    """Heuristically extract saveable facts from the conversation turn."""
    triggers = [
        # English
        "i like ", "i love ", "i enjoy ", "i prefer ",
        "i hate ", "i don't like ", "i dislike ", "i can't stand ",
        "i am ", "i'm ", "i work ", "i live ", "i study ",
        "my name is ", "my favourite ", "my favorite ",
        "i have ", "i own ", "i use ",
        # Indonesian
        "aku suka ", "aku cinta ", "aku senang ", "aku prefer ",
        "aku benci ", "aku tidak suka ", "aku ga suka ", "aku gak suka ",
        "aku adalah ", "aku ", "saya suka ", "saya adalah ",
        "saya tidak suka ", "saya benci ", "saya tinggal ", "saya kerja ",
        "namaku ", "nama saya ", "nama aku ",
        "aku tinggal ", "aku kerja ", "aku kuliah ", "aku sekolah ",
        "aku punya ", "aku pakai ", "aku lagi ", "aku sedang ",
        "aku mau ", "aku pengen ", "aku ingin ",
    ]
    facts: list[str] = []
    lower = user_input.lower()
    for trigger in triggers:
        if trigger in lower:
            fact = user_input.strip().rstrip(".")
            if fact and len(fact) < 200:
                facts.append(fact)
            break
    return facts


def _build_system_prompt_with_memory(memory: MemoryEngine, query: str) -> str:
    """Return SHIORI's system prompt optionally prefixed with relevant memories."""
    context = memory.inject_into_prompt(query)
    if context:
        return f"{context}\n\n{SHIORI_SYSTEM_PROMPT}"
    return SHIORI_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Input sources
# ---------------------------------------------------------------------------

def _get_voice_input(stt) -> str:
    """Capture one utterance from the microphone via STT."""
    return stt.listen_and_transcribe()


def _get_text_input() -> str:
    """Read one line of keyboard input from the user."""
    try:
        sys.stdout.write("You: ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        return line.strip()
    except (EOFError, KeyboardInterrupt):
        return ""


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run(
    mode: str,
    model: str,
    thinking_mode: bool,
    use_memory: bool,
    use_tts: bool,
    use_avatar: bool,
    avatar_port: int,
    stt_model: str,
    stt_device: str,
) -> None:
    """Initialise all subsystems and run the SHIORI loop."""

    print("\n" + "=" * 55)
    print(f"  SHIORI — AI Companion  |  Mode: {mode.upper()}")
    print("=" * 55 + "\n")

    # -- Avatar server (background task) ----------------------------------
    if use_avatar:
        asyncio.create_task(_start_avatar_server(avatar_port))
        local_ip = _get_local_ip()
        print(f"[Avatar] Server starting on http://{local_ip}:{avatar_port}")
        print(f"[Avatar] Open on any device: http://{local_ip}:{avatar_port}\n")

    # -- Subsystem init ---------------------------------------------------
    memory  = MemoryEngine() if use_memory else None
    speaker = TTSSpeaker(auto_detect_lang=False) if use_tts else None
    engine  = LLMEngine(model=model, thinking_mode=thinking_mode)

    # Only load STT in voice mode
    stt = None
    if mode == "voice":
        from voice.stt_listener import STTListener
        stt = STTListener(model_size=stt_model, device=stt_device)

    print("\n✅ All systems ready.\n")

    # WS broadcast helper (no-op if avatar disabled)
    async def ws_send(event: dict) -> None:
        if use_avatar:
            try:
                from server.ws_bridge import broadcast
                await broadcast(event)
            except Exception:
                pass

    greeting = "Hei! Aku SHIORI, senang bertemu denganmu~"
    print(f"[SHIORI] {greeting}")
    if speaker:
        await ws_send({"type": "speaking", "duration_ms": 2000})
        await speaker.speak(greeting)
        await ws_send({"type": "idle"})

    if mode == "text":
        print("(Text mode: ketik pesan dan tekan Enter. Ketik 'exit' untuk keluar.)\n")

    # -- Main loop --------------------------------------------------------
    while True:
        try:
            # 1. Get input
            if mode == "voice":
                transcript = _get_voice_input(stt)
            else:
                transcript = _get_text_input()

            if not transcript:
                continue

            # Exit commands for text mode
            if mode == "text" and transcript.lower() in ("exit", "quit", "keluar", "bye"):
                break

            if mode == "voice":
                print(f"\n[You] {transcript}")

            # 2. Inject memory
            if memory:
                engine.system_prompt = _build_system_prompt_with_memory(
                    memory, transcript
                )

            # 3. Get reply from LLM
            reply = ""
            async for chunk in engine.stream_reply(transcript):
                reply = chunk

            if not reply:
                continue

            print(f"[SHIORI] {reply}\n")

            # 4. Save new facts
            if memory:
                for fact in _extract_facts(transcript, reply):
                    memory.remember(fact, source="conversation")

            # 5. Speak (if TTS enabled)
            if speaker:
                # Estimate speech duration from text length (~150 wpm avg)
                est_ms = max(1000, len(reply.split()) * 400)
                await ws_send({"type": "speaking", "duration_ms": est_ms})
                await speaker.speak(reply)
                await ws_send({"type": "idle"})

        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"\n[ERROR] {exc}", file=sys.stderr)
            continue

    # -- Shutdown ---------------------------------------------------------
    if speaker:
        speaker.stop()
    print("\n[SHIORI] Goodbye! またね~\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SHIORI — AI Waifu Companion"
    )
    parser.add_argument(
        "--mode", default="voice", choices=["voice", "text"],
        help="Input mode: voice (mic) or text (keyboard). Default: voice"
    )
    parser.add_argument(
        "--model", default="qwen3:14b",
        help="Ollama model tag (default: qwen3:14b)"
    )
    parser.add_argument(
        "--think", action="store_true", default=False,
        help="Enable Qwen3 thinking mode — smarter but slower (default: off)"
    )
    parser.add_argument(
        "--no-memory", action="store_true", default=False,
        help="Disable long-term memory for this session"
    )
    parser.add_argument(
        "--no-tts", action="store_true", default=False,
        help="Disable TTS audio output (text responses only)"
    )
    parser.add_argument(
        "--no-avatar", action="store_true", default=False,
        help="Disable the Pixi.js Live2D avatar web server"
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="Avatar server port (default: 8080)"
    )
    parser.add_argument(
        "--stt-model", default="base",
        help="Whisper STT model size (default: base — multilingual)"
    )
    parser.add_argument(
        "--stt-device", default="cpu",
        help="STT inference device: cpu | cuda (default: cpu)"
    )
    args = parser.parse_args()

    asyncio.run(run(
        mode=args.mode,
        model=args.model,
        thinking_mode=args.think,
        use_memory=not args.no_memory,
        use_tts=not args.no_tts,
        use_avatar=not args.no_avatar,
        avatar_port=args.port,
        stt_model=args.stt_model,
        stt_device=args.stt_device,
    ))
