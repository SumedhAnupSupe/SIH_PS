"""Pluggable embedding backend.

Default is "hash" so the system runs without a heavy model download.
Swap EMBEDDING_BACKEND=sentence_transformers for real semantic vectors.
"""
import hashlib
import math

from app.config import settings

_sent_model = None


def _hash_embed(texts, dim):
    """Deterministic feature-hash embedding (Bag of hashed tokens)."""
    out = []
    for text in texts:
        vec = [0.0] * dim
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h // dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


def _load_sent_model():
    global _sent_model
    if _sent_model is None:
        from sentence_transformers import SentenceTransformer

        _sent_model = SentenceTransformer(settings.embedding_model)
    return _sent_model


def embed(texts, dim=None):
    """Return list[list[float]] for the given list of strings."""
    dim = dim or settings.embedding_dim
    if not texts:
        return []
    if settings.embedding_backend == "sentence_transformers":
        try:
            model = _load_sent_model()
            return [list(map(float, v)) for v in model.encode(texts)]
        except Exception as e:  # fall back to hash
            print(f"[embed] sentence_transformers failed ({e}); using hash fallback")
    return _hash_embed(texts, dim)


def compose_safety_repr(record: dict) -> str:
    """Build the entity-composed text used to embed a report (not the summary).

    record expects keys: location, task_types[], hazards[], present_precursors[],
    barrier_failure, work_changes{}.
    """
    parts = []
    if record.get("location"):
        parts.append(f"location {record['location']}")
    if record.get("task_types"):
        parts.append("task " + ", ".join(record["task_types"]))
    if record.get("hazards"):
        parts.append("hazard " + ", ".join(record["hazards"]))
    if record.get("present_precursors"):
        parts.append("precursor " + ", ".join(record["present_precursors"]))
    if record.get("barrier_failure"):
        parts.append("barrier_failure present")
    changes = record.get("work_changes") or {}
    changed = [k.replace("_", " ") for k, v in changes.items() if v]
    if changed:
        parts.append("change " + ", ".join(changed))
    return " | ".join(parts) if parts else record.get("raw_text", "")