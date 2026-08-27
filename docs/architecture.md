# SIF-AEGIS System Architecture

## Overview

SIF-AEGIS (Safety Intelligence Framework - Advanced Engine for Generating Intelligent Safety) is a serious injury/fatality precursor intelligence platform for OIL (Oil India Limited). It processes incident reports through NLP, calculates deterministic risk scores, identifies recurring safety patterns, and provides an AI-powered safety copilot.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.141 (Python) |
| ORM | SQLAlchemy 2.0 + raw SQL |
| Database | PostgreSQL 16 + pgvector |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| LLM | Google Gemini 2.0 Flash (google-genai SDK) |
| Embeddings | pgvector VECTOR(384), MiniLM-L6-v2 or hash fallback |
| Container | Docker Compose |

## High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (SPA)                     │
│  Dashboard │ Reports │ Map │ Chat │ Admin │ Barriers  │
└──────────────────────┬──────────────────────────────┘
                       │ REST API (44 endpoints)
┌──────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │   Auth   │ │ Reports  │ │ Patterns │ │  Chat  │  │
│  │  (JWT)   │ │  (NLP)   │ │ (SQL+SEM)│ │(Gemini)│  │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ Analytics│ │   Map    │ │Dashboard │ │ Barriers│  │
│  │(Temporal)│ │(GMaps)   │ │  (KPIs)  │ │ (LSR)  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ Recommendations│ │  Locations  │ │    Admin     │  │
│  │  (Evidence)  │ │  (Risk)     │ │ (Audit+Edit) │  │
│  └──────────────┘ └──────────────┘ └──────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              PostgreSQL + pgvector                    │
│  reports │ patterns │ locations │ users │ audit_log   │
│  precursors │ hazards │ barriers │ lsr │ embeddings   │
└─────────────────────────────────────────────────────┘
```

## Core Services

### Risk Engine (`backend/app/services/risk_engine.py`)
Deterministic location risk calculation using weighted formula. No ML model - pure SQL aggregation with transparent weights. Produces risk scores [0.0, 1.0] mapped to CRITICAL/HIGH/MODERATE/LOW levels.

### Pattern Engine (`backend/app/services/patterns.py`)
Two mechanisms:
- **Structured patterns**: SQL GROUP BY on (location, task, precursor) or (location, LSR)
- **Why analysis**: Lift-based driver identification (lift = in-pattern share / global share)

### Temporal Analytics (`backend/app/services/temporal.py`)
Period-over-period comparison with configurable buckets (7d/30d/90d/6m/1y). Computes SIF rates, trend direction, emerging patterns.

### Gemini Safety Copilot (`backend/app/services/gemini_service.py`)
LLM reasoning layer using Google Gemini with function calling. 7 tools execute against PostgreSQL. Gemini never computes - it calls tools and interprets results.

### RAG Fallback (`backend/app/services/rag.py`)
Query router picks SQL/vector/knowledge path. Used when Gemini is unavailable.

### Auth (`backend/app/services/auth.py`)
JWT tokens with role hierarchy: HSE_ENGINEER < MANAGER < ADMIN. Bcrypt password hashing. Append-only audit log.

## Data Flow

```
Report Submission → NLP Analysis → Precursor/LSR/Hazard Extraction
                                        ↓
                              Pattern Mining (SQL GROUP BY)
                                        ↓
                              Risk Score Calculation
                                        ↓
                              Location Risk Snapshots (historical)
                                        ↓
                              Dashboard KPIs + Map Markers
```

## API Module Map

| Router | Prefix | Endpoints |
|--------|--------|-----------|
| auth | `/api/auth` | 5 |
| reports | `/api` | 7 |
| patterns | `/api` | 4 |
| chat | `/api` | 1 |
| admin | `/api/admin` | 6 |
| recommendations | `/api` | 3 |
| locations | `/api/sif` | 4 |
| dashboard | `/api/dashboard` | 1 |
| barriers | `/api/sif` | 5 |
| analytics | `/api/analytics` | 4 |
| map | `/api/map` | 2 |
| health/config | `/api` | 2 |
| **Total** | | **44** |

## Key Design Decisions

1. **Raw SQL over ORM**: Most queries use `sqlalchemy.text()` for full control over complex analytics SQL
2. **Immutable reports**: Raw report text never modified; summaries versioned in separate table
3. **Deterministic risk**: No ML for risk scoring - transparent, auditable formulas
4. **Gemini as reasoning layer**: LLM interprets tool results, never generates statistics
5. **pgvector for embeddings**: VECTOR(384) columns on reports and knowledge_chunks
