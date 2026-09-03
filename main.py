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

Run:
    python main.py                        # voice mode (default)
    python main.py --mode text            # text mode — type instead of speak
    python main.py --mode text --no-tts   # text-only, no audio output
    python main.py --model qwen3:14b --think
    python main.py --no-memory

Dependencies:
    pip install faster-whisper sounddevice numpy edge-tts pygame ollama
"""

from __future__ import annotations

import asyncio
import argparse
import sys
from pathlib import Path

from brain.llm_engine import LLMEngine, SHIORI_SYSTEM_PROMPT
from memory.memory_engine import MemoryEngine
from voice.tts_speaker import TTSSpeaker


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
    stt_model: str,
    stt_device: str,
) -> None:
    """Initialise all subsystems and run the SHIORI loop."""

    print("\n" + "=" * 55)
    print(f"  SHIORI — AI Companion  |  Mode: {mode.upper()}")
    print("=" * 55 + "\n")

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

    greeting = "Hei! Aku SHIORI, senang bertemu denganmu~"
    print(f"[SHIORI] {greeting}")
    if speaker:
        await speaker.speak(greeting)

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
                await speaker.speak(reply)

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
        stt_model=args.stt_model,
        stt_device=args.stt_device,
    ))

