"""
voice/tts_speaker.py
────────────────────
Text-to-Speech synthesis and audio playback using Edge-TTS + pygame.

Supports multilingual voices (English, Japanese, Indonesian) with automatic
language detection, an async audio queue for non-blocking playback, and a
live ASCII progress bar while speaking.

Dependencies:
    pip install edge-tts soundfile pygame
"""

from __future__ import annotations

import asyncio
import io
import re
import tempfile
import os
from typing import Optional

import edge_tts
import pygame

# ---------------------------------------------------------------------------
# Voice presets per language
# ---------------------------------------------------------------------------

VOICE_MAP: dict[str, str] = {
    "en": "en-US-AvaNeural",       # English  – warm, natural female
    "ja": "ja-JP-NanamiNeural",    # Japanese – soft, anime-friendly female
    "id": "id-ID-GadisNeural",     # Indonesian – clear, natural female
}

_DEFAULT_LANG: str = "ja"

# Simple regex patterns for quick language detection
_LANG_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ja", re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")),       # Hiragana/Katakana/CJK
    ("id", re.compile(r"\b(aku|kamu|saya|anda|yang|dan|di|ke|dari|untuk|adalah)\b", re.I)),
]


def detect_language(text: str) -> str:
    """Heuristically detect the dominant language of *text*.

    Returns one of ``"en"``, ``"ja"``, or ``"id"``.
    Falls back to ``"en"`` when no pattern matches.
    """
    for lang, pattern in _LANG_PATTERNS:
        if pattern.search(text):
            return lang
    return _DEFAULT_LANG


# ---------------------------------------------------------------------------
# TTSSpeaker
# ---------------------------------------------------------------------------

class TTSSpeaker:
    """Synthesises text to speech via Edge-TTS and plays it through pygame.

    Parameters
    ----------
    voice_map:
        Mapping of language code → Edge-TTS voice name.
        Defaults to :data:`VOICE_MAP`.
    rate:
        Speaking rate adjustment, e.g. ``"+0%"``, ``"+10%"``, ``"-5%"``.
    volume:
        Volume adjustment, e.g. ``"+0%"``, ``"+20%"``.
    auto_detect_lang:
        If ``True``, calls :func:`detect_language` on each text to pick the
        appropriate voice automatically.  If ``False``, always uses the
        ``"en"`` voice.
    """

    def __init__(
        self,
        voice_map: dict[str, str] = VOICE_MAP,
        rate: str = "+0%",
        volume: str = "+0%",
        auto_detect_lang: bool = True,
    ) -> None:
        self.voice_map = voice_map
        self.rate = rate
        self.volume = volume
        self.auto_detect_lang = auto_detect_lang

        # Initialise pygame mixer for mp3 playback
        pygame.mixer.init()

        # Async queue: items are plain strings (text to speak)
        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._is_speaking: bool = False

        print("[TTSSpeaker] Ready.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _pick_voice(self, text: str) -> str:
        """Return the Edge-TTS voice name for the detected language."""
        if self.auto_detect_lang:
            lang = detect_language(text)
        else:
            lang = _DEFAULT_LANG
        return self.voice_map.get(lang, self.voice_map[_DEFAULT_LANG])

    @staticmethod
    def _draw_speaking_bar(frame: int, total_chars: int, label: str = "SPEAKING") -> None:
        """Print an animated ASCII progress bar while audio plays."""
        spinner = ["|", "/", "-", "\\"]
        spin = spinner[frame % len(spinner)]
        bar_width = 30
        filled = (frame % (bar_width + 1))
        # Bounce back
        if (frame // (bar_width + 1)) % 2 == 1:
            filled = bar_width - filled
        bar = "#" * filled + "." * (bar_width - filled)
        print(f"\r  TTS [{bar}] {spin} [{label:<8s}]", end="", flush=True)

    async def _synthesise_to_bytes(self, text: str, voice: str) -> bytes:
        """Call Edge-TTS and return raw MP3 bytes."""
        communicate = edge_tts.Communicate(text, voice, rate=self.rate, volume=self.volume)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        buf.seek(0)
        return buf.read()

    async def _play_mp3_bytes(self, mp3_bytes: bytes) -> None:
        """Write *mp3_bytes* to a temp file and play via pygame, showing a live bar."""
        # pygame.mixer needs a file path or file-like object; temp file is safest cross-platform
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(mp3_bytes)
            tmp_path = tmp.name

        try:
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()

            frame = 0
            self._is_speaking = True
            while pygame.mixer.music.get_busy():
                self._draw_speaking_bar(frame, 30)
                frame += 1
                await asyncio.sleep(0.08)   # ~12 fps refresh

            print()  # newline after bar
        finally:
            self._is_speaking = False
            pygame.mixer.music.unload()
            os.unlink(tmp_path)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def speak(self, text: str) -> None:
        """Synthesise *text* and play it immediately (awaitable).

        Blocks the coroutine until playback finishes.

        Parameters
        ----------
        text:
            The string to speak.  Language is auto-detected unless
            ``auto_detect_lang=False``.
        """
        if not text.strip():
            return

        # Sanitise: drop any surrogate characters that Windows cp1252 input
        # may inject — edge-tts will raise UnicodeEncodeError on them.
        text = text.encode("utf-8", errors="ignore").decode("utf-8")
        if not text.strip():
            return

        voice = self._pick_voice(text)
        lang = detect_language(text) if self.auto_detect_lang else _DEFAULT_LANG
        print(f"[TTSSpeaker] Synthesising ({lang.upper()} / {voice}) …", flush=True)

        mp3_bytes = await self._synthesise_to_bytes(text, voice)
        await self._play_mp3_bytes(mp3_bytes)

    async def enqueue(self, text: str) -> None:
        """Add *text* to the playback queue (non-blocking).

        Pair with :meth:`run_queue` running as a background task for
        sequential, non-overlapping playback.
        """
        await self._queue.put(text)

    async def run_queue(self) -> None:
        """Continuously drain the speech queue (run as a background task).

        Call ``await speaker.enqueue(None)`` to signal shutdown.
        """
        while True:
            text = await self._queue.get()
            if text is None:
                break
            await self.speak(text)
            self._queue.task_done()

    def stop(self) -> None:
        """Immediately stop current playback."""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        self._is_speaking = False


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Edge-TTS speaker test — type text, hear it spoken."
    )
    parser.add_argument(
        "--rate", default="+0%",
        help="Speaking rate adjustment, e.g. +10%% or -5%% (default: +0%%)"
    )
    parser.add_argument(
        "--volume", default="+0%",
        help="Volume adjustment, e.g. +20%% (default: +0%%)"
    )
    parser.add_argument(
        "--no-detect", action="store_true",
        help="Disable language auto-detection; always use English voice"
    )
    args = parser.parse_args()

    speaker = TTSSpeaker(
        rate=args.rate,
        volume=args.volume,
        auto_detect_lang=not args.no_detect,
    )

    async def _main() -> None:
        import sys
        # Reconfigure stdin/stdout to UTF-8 so Japanese/Indonesian characters
        # aren't corrupted by the default Windows cp1252 terminal encoding.
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

        print("\n--- TTS Speaker running. Type text and press Enter. Empty line to quit. ---\n")
        while True:
            try:
                text = input(">> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                break
            await speaker.speak(text)
        print("\n[TTSSpeaker] Stopped.")

    asyncio.run(_main())
