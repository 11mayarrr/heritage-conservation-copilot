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

    # Which damage detector to use: "heuristic" (OpenCV, uncalibrated), "mock", "synthetic_model" or "model".
    detector: str = "heuristic"

    # Regions whose confidence is below this are flagged "low confidence".
    low_confidence_threshold: float = 0.5

    # Default reference grid for walls without their own grid (see services/grids.py).
    grid_cols: int = 6
    grid_rows: int = 4

    # Image quality thresholds.
    min_width: int = 640
    min_height: int = 480
    blur_threshold: float = 60.0  # variance of Laplacian on a 1024px-wide copy
    dark_threshold: float = 45.0
    bright_threshold: float = 215.0
    clipped_fraction_max: float = 0.25

    # Camera tilt estimate (warning only, never rejects an image). Demo starting
    # values: the acceptable tilt must be set by a restoration specialist.
    tilt_frontal_deg: float = 8.0
    tilt_warn_deg: float = 20.0
    tilt_focal_factor: float = 0.75  # assumed focal length = factor x long side of the image

    # Privacy: the original upload is never written to disk; only the
    # face-anonymized copy is stored.
    face_method: str = "blur"  # "blur" or "pixelate"

    # Click-to-segment tool for the expert: "auto" uses SAM 2 when installed and
    # configured, otherwise OpenCV GrabCut. "sam2" or "grabcut" force one.
    segmenter: str = "auto"
    sam2_checkpoint: str | None = None
    sam2_config: str = "configs/sam2.1/sam2.1_hiera_t.yaml"
    sam2_model_id: str | None = None
    sam2_device: str | None = None

    # Accounts and login (step 9). Cookie is HttpOnly + SameSite=Lax; turn
    # `cookie_secure` on when the site is served over HTTPS.
    session_hours: int = 12
    cookie_secure: bool = False
    login_max_attempts: int = 5  # failed logins before the account is locked
    login_lock_minutes: int = 15
    min_password_length: int = 10

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
