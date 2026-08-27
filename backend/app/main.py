"""SIF-AEGIS main application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.api import admin, chat, patterns, recommendations, reports, locations, dashboard, barriers
from app.api import auth, analytics, map as map_api
from app.config import settings
from app.db import apply_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    apply_schema()
    # Ensure default admin user exists
    try:
        from app.db import engine
        from app.services.auth import ensure_admin_user
        from sqlalchemy.orm import Session
        with Session(engine) as db:
            ensure_admin_user(db)
    except Exception as e:
        print(f"[startup] admin user setup: {e}")
    yield


app = FastAPI(
    title="SIF-AEGIS Safety Intelligence Platform",
    version="0.4.0",
    description="Serious Injury & Fatality precursor intelligence for OIL",
    lifespan=lifespan,
)

# CORS
origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers
app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(patterns.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(recommendations.router)
app.include_router(locations.router)
app.include_router(dashboard.router)
app.include_router(barriers.router)
app.include_router(analytics.router)
app.include_router(map_api.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "sif-aegis", "version": "0.4.0"}


@app.get("/api/config")
def get_config():
    return {
        "google_maps_api_key": settings.google_maps_api_key,
        "gemini_configured": bool(settings.gemini_api_key),
    }


@app.get("/", include_in_schema=False)
def index():
    import pathlib
    html = (pathlib.Path(__file__).parent / "static" / "index.html").read_text()
    key = settings.google_maps_api_key
    html = html.replace("%%GOOGLE_MAPS_API_KEY%%", key or "")
    return HTMLResponse(content=html)
