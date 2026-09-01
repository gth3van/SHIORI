"""
memory/memory_engine.py
───────────────────────
SHIORI's long-term memory — a simple JSON-based knowledge vault.

Think of it like Obsidian: every fact SHIORI learns is saved as a note,
searchable by keyword, and injected into the LLM context when relevant.

Vault file: memory/shiori_memory.json  (auto-created on first run)

Public API
----------
remember(fact)               Save a new fact with timestamp + auto-ID
recall(query, top_n)         Keyword search → returns top N matching facts
inject_into_prompt(query)    Returns a formatted context string for the LLM
forget(fact_id)              Delete a fact by its ID
clear_all()                  Wipe the entire vault (use carefully!)
show_all()                   Print every memory (for debugging)

Dependencies: none (standard library only)
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Default vault path (sits next to this file)
# ---------------------------------------------------------------------------

_DEFAULT_VAULT = Path(__file__).parent / "shiori_memory.json"


class MemoryEngine:
    """Persistent keyword-searchable memory vault for SHIORI.

    Parameters
    ----------
    vault_path:
        Path to the JSON file used as the memory store.
        Created automatically if it does not exist.
    max_inject:
        Maximum number of memories to inject into the LLM prompt at once.
        Keeps the context window from bloating.
    """

    def __init__(
        self,
        vault_path: Path | str = _DEFAULT_VAULT,
        max_inject: int = 5,
    ) -> None:
        self.vault_path = Path(vault_path)
        self.max_inject = max_inject
        self._memories: list[dict] = []
        self._load()
        print(f"[MemoryEngine] Loaded {len(self._memories)} memories from vault.")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load memories from the JSON vault (creates empty vault if missing)."""
        if self.vault_path.exists():
            try:
                with open(self.vault_path, encoding="utf-8") as f:
                    self._memories = json.load(f)
            except (json.JSONDecodeError, OSError):
                print("[MemoryEngine] Warning: vault corrupted, starting fresh.")
                self._memories = []
        else:
            self._memories = []
            self._save()   # create the file immediately

    def _save(self) -> None:
        """Write current memories to the JSON vault."""
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.vault_path, "w", encoding="utf-8") as f:
            json.dump(self._memories, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def remember(self, fact: str, source: str = "conversation") -> str:
        """Save a new fact and return its generated ID.

        Parameters
        ----------
        fact:
            The piece of information to remember.
            e.g. ``"User dislikes spicy food"``
        source:
            Where this memory came from (``"conversation"``, ``"user_stated"``, etc.)

        Returns
        -------
        str
            The unique ID of the saved memory.
        """
        fact = fact.strip()
        if not fact:
            return ""

        # Avoid saving near-duplicate facts (simple dedup)
        fact_lower = fact.lower()
        for m in self._memories:
            if m["fact"].lower() == fact_lower:
                print(f"[MemoryEngine] Already known: '{fact}'")
                return m["id"]

        entry = {
            "id":        str(uuid.uuid4())[:8],   # short readable ID
            "fact":      fact,
            "source":    source,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self._memories.append(entry)
        self._save()
        print(f"[MemoryEngine] Remembered [{entry['id']}]: {fact}")
        return entry["id"]

    def recall(self, query: str, top_n: int = 5) -> list[dict]:
        """Keyword search over the memory vault.

        Splits *query* into individual words and scores each memory by how
        many query words appear in it.  Returns the top *top_n* matches.

        Parameters
        ----------
        query:
            Free-text search string (e.g. ``"food preference"``)
        top_n:
            Maximum number of results to return.

        Returns
        -------
        list[dict]
            Matching memory entries sorted by relevance (most relevant first).
            Each entry has keys: ``id``, ``fact``, ``source``, ``timestamp``.
        """
        if not query.strip() or not self._memories:
            return []

        keywords = set(re.findall(r"\w+", query.lower()))

        scored: list[tuple[int, dict]] = []
        for m in self._memories:
            fact_words = set(re.findall(r"\w+", m["fact"].lower()))
            score = len(keywords & fact_words)
            if score > 0:
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_n]]

    def inject_into_prompt(self, query: str) -> str:
        """Return a formatted memory context string to inject before the LLM call.

        Searches for memories relevant to *query* and formats them as a
        short block that can be prepended to the system prompt or user message.

        Returns an empty string if no relevant memories are found.

        Example output::

            [SHIORI's memory about the user]
            - User dislikes spicy food  (2026-09-01)
            - User works a 9-5 job      (2026-09-01)

        Parameters
        ----------
        query:
            The current user input — used to find contextually relevant facts.
        """
        hits = self.recall(query, top_n=self.max_inject)
        if not hits:
            return ""

        lines = ["[SHIORI's memory about the user]"]
        for m in hits:
            date = m["timestamp"][:10]   # YYYY-MM-DD only
            lines.append(f"- {m['fact']}  ({date})")

        return "\n".join(lines)

    def forget(self, fact_id: str) -> bool:
        """Delete the memory with the given ID.

        Parameters
        ----------
        fact_id:
            The short ID returned by :meth:`remember`.

        Returns
        -------
        bool
            ``True`` if the memory was found and deleted, ``False`` otherwise.
        """
        before = len(self._memories)
        self._memories = [m for m in self._memories if m["id"] != fact_id]
        if len(self._memories) < before:
            self._save()
            print(f"[MemoryEngine] Forgot memory [{fact_id}].")
            return True
        print(f"[MemoryEngine] Memory [{fact_id}] not found.")
        return False

    def clear_all(self) -> None:
        """Wipe the entire memory vault. Use with caution."""
        self._memories = []
        self._save()
        print("[MemoryEngine] All memories cleared.")

    def show_all(self) -> None:
        """Print all stored memories to the console (for debugging)."""
        if not self._memories:
            print("[MemoryEngine] Vault is empty.")
            return
        print(f"\n[MemoryEngine] Vault — {len(self._memories)} memories:")
        for m in self._memories:
            print(f"  [{m['id']}] {m['timestamp'][:10]}  {m['fact']}")
        print()

    def __len__(self) -> int:
        return len(self._memories)


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mem = MemoryEngine()

    print("\n--- Memory Engine Test ---\n")
    mem.remember("User dislikes spicy food")
    mem.remember("User has a pet cat named Mochi")
    mem.remember("User works a 9-5 office job")
    mem.remember("User likes jazz music")
    mem.remember("User lives in Jakarta, Indonesia")

    mem.show_all()

    print("Recall 'food':")
    for r in mem.recall("food"):
        print(f"  → {r['fact']}")

    print("\nInject for 'what should I eat tonight?':")
    print(mem.inject_into_prompt("what should I eat tonight?"))

    print("\n[Done]")
