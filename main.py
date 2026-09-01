"""
main.py
───────
SHIORI — Central asyncio orchestrator.

Pipeline (one loop iteration):
  1. STT listens for speech → transcript (str)
  2. MemoryEngine injects relevant facts into the LLM context
  3. LLMEngine generates SHIORI reply (thinking OFF for real-time feel)
  4. MemoryEngine auto-extracts and saves any new facts from the exchange
  5. TTSSpeaker synthesises and plays the reply

Run:
    python main.py
    python main.py --model qwen3:14b --think   # enable reasoning mode
    python main.py --no-memory                 # disable memory for testing

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
from voice.stt_listener import STTListener
from voice.tts_speaker import TTSSpeaker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_facts(user_input: str, reply: str) -> list[str]:
    """Heuristically extract saveable facts from the conversation turn.

    This is a simple keyword-triggered extraction — good enough for Phase 2.
    Phase 4 will replace this with LLM-based fact extraction.

    Triggers on phrases like:
      "I like / I love / I hate / I don't like / I am / I work / I live / my name is"
    """
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
            # Capitalise the raw user sentence as the fact
            fact = user_input.strip().rstrip(".")
            if fact and len(fact) < 200:
                facts.append(fact)
            break   # one fact per turn to avoid noise
    return facts


def _build_system_prompt_with_memory(memory: MemoryEngine, query: str) -> str:
    """Return SHIORI's system prompt optionally prefixed with relevant memories."""
    context = memory.inject_into_prompt(query)
    if context:
        return f"{context}\n\n{SHIORI_SYSTEM_PROMPT}"
    return SHIORI_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run(
    model: str,
    thinking_mode: bool,
    use_memory: bool,
    stt_model: str,
    stt_device: str,
) -> None:
    """Initialise all subsystems and run the SHIORI voice loop."""

    print("\n" + "=" * 55)
    print("  SHIORI — AI Companion  |  Starting up…")
    print("=" * 55 + "\n")

    # -- Subsystem init ---------------------------------------------------
    memory  = MemoryEngine() if use_memory else None
    speaker = TTSSpeaker(auto_detect_lang=False)   # always use Japanese voice
    stt     = STTListener(model_size=stt_model, device=stt_device)

    # LLMEngine is created fresh each loop turn so memory context updates.
    # We keep a shared history by re-using the same engine instance.
    engine = LLMEngine(model=model, thinking_mode=thinking_mode)

    print("\n✅ All systems ready.\n")
    await speaker.speak("Hei! Aku SHIORI, senang bertemu denganmu~")

    # -- Main loop --------------------------------------------------------
    while True:
        try:
            # 1. Listen
            transcript = stt.listen_and_transcribe()
            if not transcript:
                continue

            print(f"\n[You] {transcript}")

            # 2. Inject memory into system prompt for this turn
            if memory:
                engine.system_prompt = _build_system_prompt_with_memory(
                    memory, transcript
                )

            # 3. Get reply from LLM
            reply = ""
            async for chunk in engine.stream_reply(transcript):
                reply = chunk   # single-chunk response

            if not reply:
                continue

            print(f"[SHIORI] {reply}")

            # 4. Save any new facts the user just shared
            if memory:
                for fact in _extract_facts(transcript, reply):
                    memory.remember(fact, source="conversation")

            # 5. Speak
            await speaker.speak(reply)

        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"\n[ERROR] {exc}", file=sys.stderr)
            # Don't crash — log and continue listening
            continue

    # -- Shutdown ---------------------------------------------------------
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
        "--stt-model", default="base",
        help="Whisper STT model size (default: base — multilingual)"
    )
    parser.add_argument(
        "--stt-device", default="cpu",
        help="STT inference device: cpu | cuda (default: cpu)"
    )
    args = parser.parse_args()

    asyncio.run(run(
        model=args.model,
        thinking_mode=args.think,
        use_memory=not args.no_memory,
        stt_model=args.stt_model,
        stt_device=args.stt_device,
    ))
