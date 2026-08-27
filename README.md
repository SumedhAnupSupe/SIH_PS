# SIF-Aegis — Safety Intelligence Layer

Downstream intelligence layer for the SIH PS-165 NLP pipeline. It consumes your
friend's `outputs/analyses/*.json` + `outputs/sif_features_*.csv`, stores them in
PostgreSQL + pgvector, and exposes **patterns**, **related reports**, and a
**hybrid RAG copilot**.

## Scope boundary
- **DO NOT touch the NLP pipeline** (`sif_nlp/`). Ingestion contract is in
  `backend/design/ingest_contract.md`.
- This repo only implements the **downstream** layer (your part).

## Stack
- FastAPI + SQLAlchemy
- PostgreSQL 18 + `pgvector` (single DB for structured data + vectors)
- `sentence-transformers` optional; a deterministic hash embedder is the default
  so it runs without a big model download (`EMBEDDING_BACKEND=hash` → set `sentence_transformers` for quality).

## Quickstart

### 1. Database
Easiest: run the pinned Postgres+pgvector container (no system install needed):
```bash
docker run -d --name sif-pg \
  -e POSTGRES_USER=sumedhsupe -e POSTGRES_PASSWORD=sif -e POSTGRES_DB=sif_aegis \
  -p 5433:5432 pgvector/pgvector:pg16
```
Or use a system Postgres; create role/db once:
```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE sumedhsupe LOGIN PASSWORD 'sif' SUPERUSER;
CREATE DATABASE sif_aegis OWNER sumedhsupe;
SQL
```

### 2. Install
```bash
cd backend
/path/to/venv/bin/pip install -r requirements.txt
```

### 3. Ingest your friend's output
```bash
cd backend
export DATABASE_URL='postgresql+psycopg2://sumedhsupe:sif@localhost:5432/sif_aegis'
export ANALYSES_DIR='<path to sibling sif_nlp_pipeline>/outputs/analyses'
export FEATURES_DIR='<path>/outputs'
export EMBEDDING_BACKEND='hash'        # or sentence_transformers
python -m scripts.ingest
```

### 4. Load safety knowledge base (RAG docs)
Drop the source PDFs (DEKRA SIF white paper, EEI SIF precursor guide, IOGP
potential-FPI examples — already fetched into `kb_docs/`) and:
```bash
python -m scripts.load_kb ../kb_docs
```
PDFs are extracted page-aware; every chunk keeps (source, page) so RAG answers cite their origin.

### 5. Run API + UI
```bash
uvicorn app.main:app --reload --port 8000
```
- UI: http://localhost:8000/ (single-page, intentionally minimal)
- API docs: http://localhost:8000/docs

## API surface
| Endpoint | Purpose |
|---|---|
| `GET /api/reports` | list reports |
| `GET /api/reports/{incident_id}` | full report + precursor evidence, hazards, tasks, features |
| `GET /api/reports/{incident_id}/related` | v1: cosine-similar related reports + shared tags |
| `GET /api/patterns?build=true` | build (SQL) patterns, then list |
| `GET /api/patterns/{id}/reports` | v2: member reports of a pattern |
| `GET /api/patterns/{id}/why` | v2: dominance + lift — why the pattern is seen |
| `POST /api/chat` | hybrid RAG: query → SQL \| vector \| KB |
| `POST /api/patterns/{id}/recommendation` | generate evidence-grounded intervention |
| `GET /api/recommendations[?generate_missing=true]` | prioritized recommendation list |
| `GET /api/recommendations/{id}` | full evidence chain (reports + KB citations) |

### Admin mode
Admins can correct a report's **summary**, **raw text**, or its whole **analysis JSON** —
an analysis edit re-runs ingestion (entities, evidence, features, embedding) so every
consumer stays consistent. All overrides are audited (append-only `analysis_runs`) and
stamped via `reports.edited_at`. Protect with `ADMIN_API_KEY=<secret>` (header
`X-Admin-Key`); unset = open in dev mode.

| Endpoint | Purpose |
|---|---|
| `GET /api/admin/reports/{id}/editable` | fetch summary + analysis JSON for editing |
| `PUT /api/admin/reports/{id}/summary` | override summary |
| `PUT /api/admin/reports/{id}/raw-text` | override raw report text |
| `PUT /api/admin/reports/{id}/analysis` | replace analysis JSON + re-derive (`summary` optional override; current summary preserved by default) |
| `GET /api/admin/audit` | override audit trail |

## Verify end-to-end
```bash
# API running on :8000, DB ingested, then:
python scripts/smoke_test.py   # 18 checks across reports/patterns/chat/admin
```

## How the three consumers work
- **Related reports** — pgvector cosine over `reports.embedding`, enriched with "same precursor / hazard / task".
- **Pattern engine + why** — SQL GROUP BY (`location × precursor × activity`) builds patterns; `why` uses **dominance + lift** (in-pattern share ÷ global share) so only distinctive drivers surface.
- **Hybrid RAG** — a keyword query router dispatches: analytical → SQL, similar → vector(reports), knowledge → vector(knowledge_chunks) → grounded, evidence-tagged answer.

## Directory layout
```
backend/
├─ app/
│  ├─ main.py            FastAPI app
│  ├─ config.py          env config
│  ├─ db.py              engine + schema apply
│  ├─ api/               reports, patterns, chat routes
│  ├─ services/          embeddings, patterns, rag
├─ scripts/
│  ├─ ingest.py          JSON+CSV → Postgres + embeddings
│  └─ load_kb.py         safety docs → knowledge_chunks
├─ design/
│  ├─ schema.sql
│  └─ ingest_contract.md (for friend)
└─ requirements.txt
```