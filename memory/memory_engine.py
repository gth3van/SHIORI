"""
memory/memory_engine.py
-----------------------
SHIORI long-term memory -- Phase 4.

Backend:
  PRIMARY  -> VectorMemoryStore (ChromaDB) -- semantic search by MEANING
  FALLBACK -> JSON keyword vault            -- if chromadb not installed

On first run, existing shiori_memory.json entries are auto-migrated into
ChromaDB. JSON file is kept as a human-readable backup on every write.

Public API (same as Phase 2, no breaking changes):
  remember(fact)             Save a new fact
  recall(query, top_n)       Semantic/keyword search -> top N matches
  inject_into_prompt(query)  Formatted context string for the LLM
  forget(fact_id)            Delete a fact by ID
  clear_all()                Wipe everything
  show_all()                 Print all memories (debug)

Dependencies:
    pip install chromadb    (optional -- falls back to keyword if missing)
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


_DEFAULT_VAULT = Path(__file__).parent / "shiori_memory.json"


class MemoryEngine:
    """SHIORI long-term memory with semantic search (Phase 4).

    Uses ChromaDB for vector recall if available, falls back to JSON
    keyword search otherwise. JSON vault kept as backup regardless.
    """

    def __init__(
        self,
        vault_path: Path | str = _DEFAULT_VAULT,
        max_inject: int = 5,
    ) -> None:
        self.vault_path = Path(vault_path)
        self.max_inject = max_inject
        self._vector: Optional[object] = None
        self._memories: list[dict] = []   # used by fallback path only

        # Try ChromaDB vector backend
        try:
            from memory.vector_store import VectorMemoryStore
            self._vector = VectorMemoryStore(max_results=max_inject)

            # One-time migration from JSON vault
            if self.vault_path.exists() and len(self._vector) == 0:
                migrated = self._vector.import_from_json(self.vault_path)
                if migrated:
                    print(f"[MemoryEngine] Migrated {migrated} memories JSON -> ChromaDB.")

            print("[MemoryEngine] Backend: ChromaDB (semantic search)")
        except Exception as e:
            print(f"[MemoryEngine] ChromaDB unavailable ({e}), using keyword search.")
            self._vector = None
            self._load()

    # ------------------------------------------------------------------
    # JSON persistence (fallback path only)
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self.vault_path.exists():
            try:
                with open(self.vault_path, encoding="utf-8") as f:
                    self._memories = json.load(f)
            except (json.JSONDecodeError, OSError):
                print("[MemoryEngine] Vault corrupted, starting fresh.")
                self._memories = []
        else:
            self._memories = []
            self._save()

    def _save(self) -> None:
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.vault_path, "w", encoding="utf-8") as f:
            json.dump(self._memories, f, ensure_ascii=False, indent=2)

    def _sync_json_backup(self) -> None:
        if self._vector and hasattr(self._vector, "export_to_json"):
            self._vector.export_to_json(self.vault_path)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def remember(self, fact: str, source: str = "conversation") -> str:
        """Save a new fact. Returns its unique ID."""
        if self._vector:
            mem_id = self._vector.remember(fact, source=source)
            self._sync_json_backup()
            return mem_id
        # JSON fallback
        fact = fact.strip()
        if not fact:
            return ""
        for m in self._memories:
            if m["fact"].lower() == fact.lower():
                print(f"[MemoryEngine] Already known: '{fact}'")
                return m["id"]
        entry = {
            "id":        str(uuid.uuid4())[:8],
            "fact":      fact,
            "source":    source,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self._memories.append(entry)
        self._save()
        print(f"[MemoryEngine] Remembered [{entry['id']}]: {fact}")
        return entry["id"]

    def recall(self, query: str, top_n: int = 5) -> list[dict]:
        """Search memories by meaning (vector) or keyword (fallback)."""
        if self._vector:
            return self._vector.recall(query, top_n=top_n)
        # JSON keyword fallback
        if not query.strip() or not self._memories:
            return []
        keywords = set(re.findall(r"\w+", query.lower()))
        scored: list[tuple[int, dict]] = []
        for m in self._memories:
            score = len(keywords & set(re.findall(r"\w+", m["fact"].lower())))
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_n]]

    def inject_into_prompt(self, query: str) -> str:
        """Return formatted memory context string for the LLM."""
        if self._vector:
            return self._vector.inject_into_prompt(query)
        hits = self.recall(query, top_n=self.max_inject)
        if not hits:
            return ""
        lines = ["[SHIORI's memory about the user]"]
        for m in hits:
            lines.append(f"- {m['fact']}  ({m['timestamp'][:10]})")
        return "\n".join(lines)

    def forget(self, fact_id: str) -> bool:
        """Delete a memory by ID. Returns True if deleted."""
        if self._vector:
            result = self._vector.forget(fact_id)
            self._sync_json_backup()
            return result
        before = len(self._memories)
        self._memories = [m for m in self._memories if m["id"] != fact_id]
        if len(self._memories) < before:
            self._save()
            print(f"[MemoryEngine] Forgot [{fact_id}].")
            return True
        print(f"[MemoryEngine] [{fact_id}] not found.")
        return False

    def clear_all(self) -> None:
        """Wipe the entire memory vault."""
        if self._vector:
            self._vector.clear_all()
            self._sync_json_backup()
            return
        self._memories = []
        self._save()
        print("[MemoryEngine] All memories cleared.")

    def show_all(self) -> None:
        """Print all memories to console (debugging)."""
        if self._vector:
            self._vector.show_all()
            return
        if not self._memories:
            print("[MemoryEngine] Vault is empty.")
            return
        print(f"\n[MemoryEngine] Vault -- {len(self._memories)} memories:")
        for m in self._memories:
            print(f"  [{m['id']}] {m['timestamp'][:10]}  {m['fact']}")
        print()

    def __len__(self) -> int:
        if self._vector:
            return len(self._vector)
        return len(self._memories)


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mem = MemoryEngine()
    print("\n--- MemoryEngine Test (Phase 4 Semantic Search) ---\n")

    mem.remember("User dislikes spicy food")
    mem.remember("User has a pet cat named Mochi")
    mem.remember("User works a 9-5 office job")
    mem.remember("User likes jazz music")
    mem.remember("User lives in Jakarta, Indonesia")
    mem.remember("User is developing an AI companion called SHIORI")

    mem.show_all()

    print("Semantic recall: 'what food does the user hate?'")
    for r in mem.recall("what food does the user hate?"):
        print(f"  [{r.get('score', '')}] {r['fact']}")

    print("\nInject for 'aku lapar mau makan apa ya':")
    print(mem.inject_into_prompt("aku lapar mau makan apa ya"))

    print("\n[Done]")
