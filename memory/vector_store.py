"""
memory/vector_store.py
──────────────────────
ChromaDB-powered semantic memory store for SHIORI — Phase 4.

Why vector search beats keyword search
───────────────────────────────────────
Phase 2 (keyword): "I am cold" misses "user lives somewhere cold at night"
Phase 4 (vector):  "I am cold" finds it because the MEANING is similar.

Storage (all local, inside memory/):
  memory/chroma_db/          <- ChromaDB persistent database directory
  memory/shiori_memory.json  <- JSON vault still kept as human-readable backup

Embedding model: ChromaDB default (sentence-transformers/all-MiniLM-L6-v2)
  ~80MB download on first run, cached after that.
  Runs 100% on CPU. No API key needed.

Dependencies:
    pip install chromadb
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import chromadb
    from chromadb.config import Settings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False


_DEFAULT_DB_DIR     = Path(__file__).parent / "chroma_db"
_DEFAULT_COLLECTION = "shiori_memories"
_DEFAULT_MAX_RESULTS = 5


class VectorMemoryStore:
    """Semantic memory vault backed by ChromaDB.

    Memories are stored as vector embeddings. Recall searches by MEANING,
    not just keyword overlap — so SHIORI understands context even when the
    user phrases things differently each time.

    Parameters
    ----------
    db_dir:
        Directory where ChromaDB persists its data. Created automatically.
    collection_name:
        Name of the ChromaDB collection to use.
    max_results:
        Maximum number of memories returned per recall query.
    """

    def __init__(
        self,
        db_dir: Path | str = _DEFAULT_DB_DIR,
        collection_name: str = _DEFAULT_COLLECTION,
        max_results: int = _DEFAULT_MAX_RESULTS,
    ) -> None:
        if not _CHROMA_AVAILABLE:
            raise ImportError("chromadb not installed. Run: pip install chromadb")

        self.db_dir = Path(db_dir)
        self.max_results = max_results
        self.db_dir.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(self.db_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        print(f"[VectorStore] Ready -- {self._col.count()} memories loaded.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def remember(self, fact: str, source: str = "conversation") -> str:
        """Embed and store a new memory. Returns its ID.

        Skips near-duplicates automatically (cosine distance < 0.03).
        """
        fact = fact.strip()
        if not fact:
            return ""

        # Semantic dedup
        if self._col.count() > 0:
            existing = self._col.query(
                query_texts=[fact],
                n_results=1,
                include=["distances"],
            )
            distances = existing.get("distances", [[]])[0]
            if distances and distances[0] < 0.03:
                existing_ids = existing.get("ids", [[]])[0]
                print(f"[VectorStore] Near-duplicate skipped: '{fact[:60]}'")
                return existing_ids[0] if existing_ids else ""

        memory_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat(timespec="seconds")

        self._col.add(
            ids=[memory_id],
            documents=[fact],
            metadatas=[{
                "source":    source,
                "timestamp": timestamp,
                "fact":      fact,
            }],
        )
        print(f"[VectorStore] Remembered [{memory_id}]: {fact[:80]}")
        return memory_id

    def recall(self, query: str, top_n: Optional[int] = None) -> list[dict]:
        """Semantic search -- find memories relevant to query by meaning.

        Returns list of dicts with keys: id, fact, source, timestamp, score.
        """
        if not query.strip() or self._col.count() == 0:
            return []

        n = min(top_n or self.max_results, self._col.count())
        results = self._col.query(
            query_texts=[query],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        memories: list[dict] = []
        ids       = results.get("ids",       [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for mem_id, meta, dist in zip(ids, metadatas, distances):
            score = round(1.0 - dist, 4)
            if score < 0.3:   # skip very weak matches
                continue
            memories.append({
                "id":        mem_id,
                "fact":      meta.get("fact", ""),
                "source":    meta.get("source", ""),
                "timestamp": meta.get("timestamp", ""),
                "score":     score,
            })

        return memories

    def inject_into_prompt(self, query: str) -> str:
        """Return formatted memory context string for the LLM.

        Returns empty string if nothing relevant found.
        """
        hits = self.recall(query)
        if not hits:
            return ""

        lines = ["[SHIORI's memory about the user]"]
        for m in hits:
            date  = m["timestamp"][:10]
            score = m["score"]
            lines.append(f"- {m['fact']}  ({date}) [relevance: {score}]")

        return "\n".join(lines)

    def forget(self, memory_id: str) -> bool:
        """Delete a memory by ID. Returns True if deleted."""
        try:
            self._col.delete(ids=[memory_id])
            print(f"[VectorStore] Forgot [{memory_id}].")
            return True
        except Exception:
            print(f"[VectorStore] Memory [{memory_id}] not found.")
            return False

    def clear_all(self) -> None:
        """Wipe all memories from the vector store."""
        self._client.delete_collection(_DEFAULT_COLLECTION)
        self._col = self._client.get_or_create_collection(
            name=_DEFAULT_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        print("[VectorStore] All memories cleared.")

    def export_to_json(self, path: Path | str) -> None:
        """Export all memories to JSON file (human-readable backup)."""
        path = Path(path)
        if self._col.count() == 0:
            path.write_text("[]", encoding="utf-8")
            return

        results = self._col.get(include=["metadatas"])
        entries = [
            {
                "id":        mem_id,
                "fact":      meta.get("fact", ""),
                "source":    meta.get("source", ""),
                "timestamp": meta.get("timestamp", ""),
            }
            for mem_id, meta in zip(results["ids"], results["metadatas"])
        ]
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[VectorStore] Exported {len(entries)} memories -> {path}.")

    def import_from_json(self, path: Path | str) -> int:
        """Import memories from a JSON file (migrates from Phase 2 JSON vault)."""
        path = Path(path)
        if not path.exists():
            return 0

        entries = json.loads(path.read_text(encoding="utf-8"))
        imported = 0
        for e in entries:
            fact = e.get("fact", "").strip()
            if fact:
                self.remember(fact, source=e.get("source", "import"))
                imported += 1

        print(f"[VectorStore] Imported {imported} memories from {path}.")
        return imported

    def show_all(self) -> None:
        """Print all memories to console (debugging)."""
        if self._col.count() == 0:
            print("[VectorStore] Vault is empty.")
            return

        results = self._col.get(include=["metadatas"])
        print(f"\n[VectorStore] Vault -- {len(results['ids'])} memories:")
        for mem_id, meta in zip(results["ids"], results["metadatas"]):
            ts   = meta.get("timestamp", "")[:10]
            fact = meta.get("fact", "")
            print(f"  [{mem_id}] {ts}  {fact}")
        print()

    def __len__(self) -> int:
        return self._col.count()


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n--- VectorMemoryStore Test ---\n")
    store = VectorMemoryStore()

    store.remember("User dislikes spicy food")
    store.remember("User has a pet cat named Mochi")
    store.remember("User works a 9-5 office job")
    store.remember("User likes jazz music and plays guitar")
    store.remember("User lives in Jakarta, Indonesia")
    store.remember("User is developing an AI companion called SHIORI")

    store.show_all()

    print("Semantic recall: 'what food does user avoid?'")
    for r in store.recall("what food does user avoid?"):
        print(f"  [{r['score']:.2f}] {r['fact']}")

    print("\nSemantic recall: 'does the user have any pets?'")
    for r in store.recall("does the user have any pets?"):
        print(f"  [{r['score']:.2f}] {r['fact']}")

    print("\nInject for 'aku lapar nih':")
    print(store.inject_into_prompt("aku lapar nih"))
