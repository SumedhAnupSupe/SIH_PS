"""Load safety-standards documents (DEKRA / EEI / IOGP / OISD) into the KB.

Usage:
    python -m scripts.load_kb <dir-with-pdf-or-txt-docs>

Each PDF/TXT is split into overlapping chunks that keep their page number,
embedded, and stored in knowledge_chunks — so every RAG answer can cite
(source document, page).
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import text as sa_text

from app.config import settings
from app.db import apply_schema, engine
from app.services.embeddings import embed

CHUNK_CHARS = 900
OVERLAP = 150


def _vec(v) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def extract_pages(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return [(page_no, text)] — page numbers are 1-based."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [
            (i + 1, p.extract_text() or "") for i, p in enumerate(reader.pages)
        ]
    return [(1, path.read_text())]


def chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    """Sliding window over concatenated page text; chunks remember their page."""
    buf, start_page = "", pages[0][0] if pages else 1
    out = []
    for page_no, txt in pages:
        txt = " ".join(txt.split())
        if not txt:
            continue
        if not buf:
            start_page = page_no
        while len(buf) + len(txt) >= CHUNK_CHARS:
            take = CHUNK_CHARS - len(buf)
            buf += " " + txt[:take]
            out.append({"text": buf.strip(), "page": start_page})
            txt = txt[take - OVERLAP:] if len(txt) > take - OVERLAP else ""
            buf, start_page = "", page_no
        buf += " " + txt
    if buf.strip():
        out.append({"text": buf.strip(), "page": start_page})
    return [c for c in out if len(c["text"]) > 80]  # drop tiny fragments


def load_file(conn, path: pathlib.Path):
    src = path.stem.split("_")[0].upper()
    name = path.stem
    doc_id = conn.execute(
        sa_text("SELECT id FROM knowledge_documents WHERE path=:p"), {"p": str(path)}
    ).scalar()
    if not doc_id:
        doc_id = conn.execute(
            sa_text("INSERT INTO knowledge_documents (source, name, path) VALUES (:s,:n,:p) RETURNING id"),
            {"s": src, "n": name, "p": str(path)},
        ).scalar()

    chunks = chunk_pages(extract_pages(path))
    # replace previous chunks of this doc
    conn.execute(sa_text("DELETE FROM knowledge_chunks WHERE document_id=:d"), {"d": doc_id})
    vecs = embed([c["text"] for c in chunks])
    for c, v in zip(chunks, vecs):
        conn.execute(
            sa_text(
                "INSERT INTO knowledge_chunks (document_id, chunk_text, metadata, embedding) "
                "VALUES (:d,:t,:m,:v)"
            ),
            {"d": doc_id, "t": c["text"],
             "m": json.dumps({"source": src, "name": name, "page": c["page"]}),
             "v": _vec(v)},
        )
    return len(chunks)


def main(kb_dir: str = ""):
    apply_schema()
    root = pathlib.Path(kb_dir or os.environ.get("KB_DIR", ""))
    if not root.is_dir():
        print(f"[kb] dir not found: {root} — pass a directory as argv[1]")
        return
    files = sorted(p for p in root.iterdir() if p.suffix.lower() in (".pdf", ".txt"))
    if not files:
        print(f"[kb] no pdf/txt files in {root}")
        return
    with engine.begin() as conn:
        for f in files:
            n = load_file(conn, f)
            print(f"[kb] {f.name}: {n} chunks embedded")
    print("[kb] done")


if __name__ == "__main__":
    import os

    main(sys.argv[1] if len(sys.argv) > 1 else "")
