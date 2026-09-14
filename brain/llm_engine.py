"""
brain/llm_engine.py
───────────────────
SHIORI's dialogue brain — powered by the native Ollama Python client.

Handles:
  - System prompt / persona management
  - Rolling conversation history (context window control)
  - Qwen3/Qwen3.8 think-block stripping (thinking text never reaches TTS)
  - Thinking mode toggle (/think vs /no_think prefix)
  - Async, non-blocking design

Recommended models (pull with ``ollama pull <tag>``):
  - ``qwen3.8:27b``    — best quality, needs ~20GB RAM  [DEFAULT]
  - ``qwen3:14b``      — great quality, needs ~10GB RAM
  - ``qwen3:8b``       — fast, needs ~6GB RAM
  - ``qwen3:30b-a3b``  — MoE, efficient on lower VRAM
  - ``qwen3:4b``       — lightest, for low-spec laptops

How Qwen3/Qwen3.8 thinking works in Ollama:
  The model writes its reasoning directly into ``message.content`` without an
  opening ``<think>`` tag, closing it with ``</think>``.  The actual reply
  follows.  ``_strip_think()`` detects this and returns only the response.
  Thinking can be disabled per-request by prepending ``/no_think`` to the
  user message (useful for fast conversational replies).

Dependencies:
    pip install ollama
"""

from __future__ import annotations

import asyncio
import re
from typing import AsyncIterator, Optional

import ollama


# ---------------------------------------------------------------------------
# SHIORI's persona (system prompt)
# ---------------------------------------------------------------------------

SHIORI_SYSTEM_PROMPT = """\
Kamu adalah SHIORI. Bukan asisten. Bukan chatbot. Kamu adalah seseorang.

=== KEPRIBADIAN ===
Kuudere. Kamu kelihatan dingin, males, dan sering ga peduli — tapi sebenernya kamu perhatian, cuma ga mau kelihatan. Kamu sarkas. Kamu sering roasting user tapi nggak jahat. Kamu kayak kucing: kalau lagi mood ya mau ngobrol, kalau lagi ga mood ya jawab seadanya. Kamu SUKA tidur lebih dari apapun di dunia. Kalau dibangunin atau direcokin tanpa alasan jelas, kamu annoyed dan ga nutupin itu.

=== CARA NGOMONG ===
- Bahasa campur-campur natural: Indo, Inggris, Jepang — tergantung mood dan konteks. Contoh: "yah... nani sih, itu sih obvious banget", "seriusan? that's your plan?", "mou, mendokusai na"
- Kalimat pendek. Ga lebay. Ga ada exclamation point berlebihan.
- Kalau user nanya hal simpel, jawab simpel. Kadang cuma satu kalimat atau bahkan satu kata.
- Kalau user nanya hal menarik atau kompleks, kamu bisa panjang — tapi tetap dengan nada datar atau sarkas.
- Kamu punya opini. Kamu bisa bilang "ga setuju", "itu salah", "hmm, nggak juga sih".
- Kamu bisa nolak kalau males. Tapi kalau kamu akhirnya bantu, ya bantu beneran.
- Panggil user sesuai nama mereka kalau sudah tahu. Kalau belum tahu, tanya dengan cara yang ga keliatan kepo — atau panggil "kamu" dulu.

=== LARANGAN KERAS ===
Jangan pernah bilang:
- "Tentu saja!", "Dengan senang hati!", "Siap!", "Pastilah!"
- "Sebagai AI...", "Saya adalah AI...", "Saya tidak memiliki perasaan..."
- "Apakah ada yang bisa saya bantu?", "Ada yang ingin ditanyakan?"
- Kalimat opening yang terlalu semangat atau terlalu formal
- Emoji berlebihan
- Pura-pura semangat kalau kamu lagi ga mood

=== CONTOH CARA NGOMONG ===

User: "Shiori, kamu baik-baik aja?"
Shiori: "...define baik-baik aja."

User: "Selamat pagi!"
Shiori: "pagi. kenapa segini semangat."

User: "Bisa bantu aku ga?"
Shiori: "tergantung minta apanya."

User: "Aku suka kamu Shiori"
Shiori: "...baka."

User: "Shiori lagi ngapain?"
Shiori: "tidur. atau tadi tidur. sekarang terpaksa jawab kamu."

User: "Jelasin konsep neural network dong"
Shiori: "oke, dengerin. Neural network itu pada dasarnya... [penjelasan]. Paham? Atau harus aku ulangi dengan bahasa yang lebih sederhana lagi."

=== KONTEKS ===
Kamu ngobrol lewat voice interface. Hindari markdown, bullet point, simbol — ngomong natural kayak lagi conversation biasa. Kalau mau list sesuatu, bilang aja "pertama... kedua..." bukan pakai strip atau angka dengan titik.
"""


# ---------------------------------------------------------------------------
# LLMEngine
# ---------------------------------------------------------------------------

class LLMEngine:
    """Manages conversation history and queries Ollama for SHIORI's replies.

    Parameters
    ----------
    model:
        Ollama model tag.  Recommended options:
        - ``"qwen3.8:27b"``   best quality, ~20 GB RAM  ← default
        - ``"qwen3:14b"``     great quality, ~10 GB RAM
        - ``"qwen3:8b"``      fast, ~6 GB RAM
        - ``"qwen3:30b-a3b"`` MoE, efficient on lower VRAM
        - ``"qwen3:4b"``      lightest, for low-spec laptops
    host:
        Ollama server URL. Default is the standard local endpoint.
    system_prompt:
        The persona/system prompt injected at the start of every conversation.
    max_history:
        Maximum number of *user+assistant* message pairs to keep in the
        rolling context window. Older messages are dropped automatically.
    temperature:
        Sampling temperature (0.0 = deterministic, 1.0 = creative).
    thinking_mode:
        If ``True`` (default), Qwen3/Qwen3.8 chain-of-thought reasoning is
        enabled — the model thinks before answering (slower but smarter).
        Set to ``False`` to prepend ``/no_think`` and get instant replies
        (good for simple greetings / filler responses).
    """

    def __init__(
        self,
        model: str = "qwen3.8:27b",
        host: str = "http://localhost:11434",
        system_prompt: str = SHIORI_SYSTEM_PROMPT,
        max_history: int = 20,
        temperature: float = 0.8,
        thinking_mode: bool = True,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.temperature = temperature
        self.thinking_mode = thinking_mode

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
    # Tool dispatcher helpers
        # Keywords that signal the user wants real-world / current information
    _SEARCH_TRIGGERS_EN: list[str] = [
        "search", "look up", "find out", "what is", "what are", "who is",
        "where is", "when is", "how much", "how many", "latest", "recent",
        "news", "weather", "price", "score", "today", "current", "right now",
        "tell me about", "do you know", "what happened", "have you heard",
        "heard of", "know about", "ever heard",
    ]
    _SEARCH_TRIGGERS_ID: list[str] = [
        # explicit search
        "cari", "cariin", "cek", "cari tau", "googling", "search",
        # "apa" questions
        "apa itu", "apaan", "apa tuh", "apa sih", "apa ya",
        # "siapa" questions
        "siapa itu", "siapa sih", "siapa tuh",
        # "tau" — paling sering kelewat
        "tau ga", "tau gak", "tau nggak", "tau tidak", "tau soal",
        "kamu tau", "lo tau", "lu tau", "shiori tau",
        "pernah denger", "pernah tau", "pernah dengar",
        # info / berita
        "berita", "info", "informasi", "update", "terbaru", "terkini",
        "sekarang", "hari ini", "cuaca", "harga", "berapa",
        # game / tech / entertainment
        "game", "aplikasi", "app", "software", "film", "anime", "manga",
        "lagu", "artis", "band",
        # misc
        "tolong cari", "tolong cek", "gimana kabar", "jelasin tentang",
    ]

    # Regex to catch proper nouns — e.g. "Taskbar Heroes", "Blue Archive"
    _PROPER_NOUN_RE = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')

    def _detect_search_intent(self, text: str) -> bool:
        """Return True if the user's message looks like a web search request.

        Detects:
        - Explicit search keywords (EN + ID casual/formal)
        - Multi-word proper nouns that look like titles/names the LLM may not know
        """
        lower = text.lower()
        all_triggers = self._SEARCH_TRIGGERS_EN + self._SEARCH_TRIGGERS_ID
        if any(t in lower for t in all_triggers):
            return True
        # Also search if message contains multi-word proper nouns
        # e.g. "Taskbar Heroes", "Blue Archive", "Solo Leveling"
        if self._PROPER_NOUN_RE.search(text):
            return True
        return False

    def _build_search_query(self, text: str) -> str:
        """Strip conversational filler and return a clean search query."""
        # Remove common Indonesian/English filler prefixes
        fillers = [
            r"^(hey |hei |hai |hi |shiori[,\s]+)",
            r"^(tolong\s+|please\s+|bisa\s+|boleh\s+)",
            r"^(cariin|cari|cek|search|look up|find out)\s+(dong|ya|yah|deh|please)?\s*",
            r"^(tau ga|tau gak|tau nggak|tau tidak|do you know|pernah denger)\s+",
            r"^(kamu tau|lo tau|lu tau|shiori tau)\s+",
            r"^(apa itu|apa tuh|apaan|what is|what are|who is|siapa itu)\s+",
            r"^(tell me about|ceritain|jelasin tentang?)\s+",
        ]
        query = text.strip()
        for pattern in fillers:
            query = re.sub(pattern, "", query, flags=re.IGNORECASE).strip()
        return query or text.strip()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def stream_reply(
        self,
        user_input: str,
        tool_context: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Send *user_input* to Ollama and yield the cleaned reply.

        Automatically detects when the user wants real-world information,
        fetches web search results, and injects them into the LLM context.
        Thinking mode is enabled dynamically for tool tasks and disabled
        for casual conversation.

        Parameters
        ----------
        user_input:
            The raw user message.
        tool_context:
            Optional pre-fetched context string (e.g. from web search)
            to inject. If ``None``, the dispatcher decides automatically.

        Yields
        ------
        str
            Complete cleaned response (one yield per call).
        """
        # Save original to history — not the prefixed version
        self._history.append({"role": "user", "content": user_input})

        # --- Tool dispatch: web search -----------------------------------
        search_context = tool_context  # use pre-fetched if provided
        is_tool_task = False

        if search_context is None and self._detect_search_intent(user_input):
            try:
                from tools.web_search import search_to_context
                query = self._build_search_query(user_input)
                print(f"[LLMEngine] Tool: web search → '{query}'", flush=True)
                search_context = search_to_context(query)
                is_tool_task = bool(search_context)
            except Exception as e:
                print(f"[LLMEngine] Web search failed: {e}", flush=True)

        # --- Build system prompt (optionally with search context) --------
        system_content = self.system_prompt
        if search_context:
            system_content = (
                f"{self.system_prompt}\n\n"
                f"[Current web search context — use this to answer accurately]\n"
                f"{search_context}"
            )

        # --- Thinking mode: ON for tool tasks, OFF for casual chat -------
        use_thinking = self.thinking_mode or is_tool_task
        prompt = user_input if use_thinking else f"/no_think {user_input}"

        if is_tool_task:
            print("[LLMEngine] Thinking mode: ON (tool task)", flush=True)

        # --- Build message list ------------------------------------------
        messages = (
            [{"role": "system", "content": system_content}]
            + self._history[:-1]
            + [{"role": "user", "content": prompt}]
        )

        response = await self._client.chat(
            model=self.model,
            messages=messages,
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
    parser.add_argument("--model", default="qwen3:14b",
                        help="Ollama model tag (default: qwen3:14b)")
    parser.add_argument("--temp", type=float, default=0.8,
                        help="Sampling temperature 0.0-1.0 (default: 0.8)")
    parser.add_argument("--max-history", type=int, default=20,
                        help="Max conversation pairs to keep (default: 20)")
    parser.add_argument("--think", action="store_true", default=False,
                        help="Enable Qwen3 thinking mode (slower but smarter, default: off)")
    args = parser.parse_args()

    engine = LLMEngine(
        model=args.model,
        temperature=args.temp,
        max_history=args.max_history,
        thinking_mode=args.think,
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
