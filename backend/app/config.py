import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    db_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://sumedhsupe:sif@localhost:5433/sif_aegis"
    )
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "hash")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "384"))
    analyses_dir: str = os.getenv("ANALYSES_DIR", "")
    features_dir: str = os.getenv("FEATURES_DIR", "")
    top_k: int = int(os.getenv("TOP_K", "10"))
    admin_key: str = os.getenv("ADMIN_API_KEY", "")
    google_maps_api_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    jwt_secret: str = os.getenv("JWT_SECRET", "sif-aegis-dev-secret-change-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    app_env: str = os.getenv("APP_ENV", "development")
    cors_origins: list = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "*").split(","))


settings = Settings()
