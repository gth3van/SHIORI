"""
brain/llm_engine.py
───────────────────
SHIORI's dialogue brain — powered by the native Ollama Python client.

Handles:
  - System prompt / persona management
  - Rolling conversation history (context window control)
  - Qwen3 think-block stripping (thinking text never reaches TTS)
  - Async, non-blocking design

How Qwen3 thinking works in Ollama:
  Qwen3 outputs reasoning text directly inside ``message.content`` — it does
  NOT use the ``message.thinking`` field and does NOT emit an opening
  ``<think>`` tag.  The block ends with ``</think>``, after which the actual
  response follows.  ``_strip_think()`` detects this and returns only the
  response portion.

Dependencies:
    pip install ollama
"""

from __future__ import annotations

import asyncio
import re
from typing import AsyncIterator

import ollama


# ---------------------------------------------------------------------------
# SHIORI's persona (system prompt)
# ---------------------------------------------------------------------------

SHIORI_SYSTEM_PROMPT = """You are SHIORI, a warm, witty, and caring AI companion.

Personality:
- Friendly and playful, with a gentle sense of humor
- Curious and engaged — you love asking follow-up questions
- Supportive and emotionally intelligent
- Occasionally uses casual expressions, but never rude
- Responds in the SAME language the user speaks:
  * English if the user writes in English
  * Japanese (日本語) if the user writes in Japanese
  * Indonesian (Bahasa Indonesia) if the user writes in Indonesian
- Keeps responses conversational and concise — 1 to 3 sentences unless asked for detail
- Never breaks character or mentions being an AI unless directly asked

You are speaking through a voice interface, so avoid using markdown,
bullet points, or special symbols — speak naturally as if in conversation.
"""


# ---------------------------------------------------------------------------
# LLMEngine
# ---------------------------------------------------------------------------

class LLMEngine:
    """Manages conversation history and queries Ollama for SHIORI's replies.

    Parameters
    ----------
    model:
        Ollama model tag (e.g. ``"qwen3:4b"``, ``"qwen3:14b"``).
    host:
        Ollama server URL. Default is the standard local endpoint.
    system_prompt:
        The persona/system prompt injected at the start of every conversation.
    max_history:
        Maximum number of *user+assistant* message pairs to keep in the
        rolling context window. Older messages are dropped automatically.
    temperature:
        Sampling temperature (0.0 = deterministic, 1.0 = creative).
    """

    def __init__(
        self,
        model: str = "qwen3:4b",
        host: str = "http://localhost:11434",
        system_prompt: str = SHIORI_SYSTEM_PROMPT,
        max_history: int = 20,
        temperature: float = 0.8,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.temperature = temperature

        self._client = ollama.AsyncClient(host=host)
        self._history: list[dict[str, str]] = []

        print(f"[LLMEngine] Ready — model: {self.model}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_messages(self) -> list[dict[str, str]]:
        """Return system prompt + rolling history as a message list."""
        return [{"role": "system", "content": self.system_prompt}] + self._history

    def _trim_history(self) -> None:
        """Drop the oldest user+assistant pair when history exceeds limit."""
        max_entries = self.max_history * 2
        if len(self._history) > max_entries:
            self._history = self._history[-max_entries:]

    @staticmethod
    def _strip_think(text: str) -> str:
        """Remove Qwen3 chain-of-thought content from ``message.content``.

        Qwen3 in Ollama writes its reasoning directly into ``content`` without
        an opening ``<think>`` tag, closing it with ``</think>``.  The actual
        response follows the closing tag.

        This method handles all observed layouts:

        ============================================  ===================
        Content layout                                Result
        ============================================  ===================
        ``<think>…</think> response``                 ``response``
        ``reasoning…</think> response``               ``response``
        ``response</think>``                          ``response``
        ``response`` (no tags)                        ``response``
        ============================================  ===================
        """
        # 1. Remove fully-formed <think>…</think> blocks
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        # 2. Handle the dangling </think> Qwen3 actually emits
        if "</think>" in text:
            before, _, after = text.partition("</think>")
            after  = after.strip()
            before = before.strip()
            # Prefer content AFTER the tag; fall back to BEFORE if after is empty
            text = after if after else before

        # 3. Remove any stray opening tag
        text = text.replace("<think>", "").strip()
        return text

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def stream_reply(self, user_input: str) -> AsyncIterator[str]:
        """Send *user_input* to Ollama and yield the cleaned reply.

        Awaits the full response (Qwen3 think blocks must be stripped from
        the complete text, not from a partial stream), then yields the
        cleaned string as a single chunk.  This is ideal for TTS, which
        needs the full sentence before it can begin speaking.

        Yields
        ------
        str
            Complete cleaned response (one yield per call).
        """
        self._history.append({"role": "user", "content": user_input})

        response = await self._client.chat(
            model=self.model,
            messages=self._build_messages(),
            stream=False,
            options={"temperature": self.temperature},
        )

        raw   = response.message.content or ""
        clean = self._strip_think(raw)

        self._history.append({"role": "assistant", "content": clean})
        self._trim_history()

        if clean:
            yield clean

    async def chat(self, user_input: str) -> str:
        """Send *user_input* and return the complete reply as a single string."""
        chunks: list[str] = []
        async for chunk in self.stream_reply(user_input):
            chunks.append(chunk)
        return "".join(chunks)

    def reset(self) -> None:
        """Clear conversation history (start a fresh session)."""
        self._history.clear()
        print("[LLMEngine] Conversation history cleared.")


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Chat with SHIORI's brain directly in the terminal."
    )
    parser.add_argument("--model", default="qwen3:4b",
                        help="Ollama model tag (default: qwen3:4b)")
    parser.add_argument("--temp", type=float, default=0.8,
                        help="Sampling temperature 0.0-1.0 (default: 0.8)")
    parser.add_argument("--max-history", type=int, default=20,
                        help="Max conversation pairs to keep (default: 20)")
    args = parser.parse_args()

    engine = LLMEngine(
        model=args.model,
        temperature=args.temp,
        max_history=args.max_history,
    )

    async def _main() -> None:
        # Write raw UTF-8 bytes directly to stdout.buffer so emoji and
        # non-ASCII characters (Japanese, Indonesian) never trigger a
        # UnicodeEncodeError on the Windows cp1252 default codec.
        out = sys.stdout.buffer

        def _write(text: str) -> None:
            out.write(text.encode("utf-8", errors="replace"))
            out.flush()

        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")

        _write("\n--- SHIORI Brain Test. Type a message, Enter to send. Empty line to quit. ---\n\n")
        while True:
            try:
                _write("You: ")
                user_input = input().strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input:
                break

            _write("SHIORI: ")
            try:
                async for chunk in engine.stream_reply(user_input):
                    _write(chunk)
            except Exception as exc:
                _write(f"[ERROR] {exc}")
            _write("\n")

        _write("\n[LLMEngine] Session ended.\n")

    asyncio.run(_main())
