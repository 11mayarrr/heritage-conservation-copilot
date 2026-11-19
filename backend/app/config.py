"""Application settings, read from environment variables (see .env.example)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HCC_", extra="ignore")

    # Database: SQLite for local dev/tests, PostgreSQL in docker-compose.
    database_url: str = f"sqlite:///{REPO_ROOT / 'data' / 'hcc.db'}"

    # Object storage (local folder; swap the Storage class for S3/Supabase later).
    storage_dir: Path = REPO_ROOT / "data" / "storage"

    knowledge_base_dir: Path = REPO_ROOT / "knowledge_base"

    # Which damage detector to use: "heuristic" (OpenCV, uncalibrated) or "mock".
    detector: str = "heuristic"

    # Regions whose confidence is below this are flagged "low confidence".
    low_confidence_threshold: float = 0.5

    # Reference grid laid over each wall photo (temporary until an official grid exists).
    grid_cols: int = 6
    grid_rows: int = 4

    # Image quality thresholds.
    min_width: int = 640
    min_height: int = 480
    blur_threshold: float = 60.0  # variance of Laplacian on a 1024px-wide copy
    dark_threshold: float = 45.0
    bright_threshold: float = 215.0
    clipped_fraction_max: float = 0.25

    # Privacy: the original upload is never written to disk; only the
    # face-anonymized copy is stored.
    face_method: str = "blur"  # "blur" or "pixelate"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
