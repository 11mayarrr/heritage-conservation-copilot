from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="session")
def samples(tmp_path_factory) -> Path:
    from make_synthetic_samples import make_pair

    return make_pair(tmp_path_factory.mktemp("samples"))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HCC_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("HCC_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("HCC_DETECTOR", "heuristic")
    from app import config
    from app.services import storage

    config.get_settings.cache_clear()
    storage._storage = None
    from app.database.session import init_engine

    init_engine()
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    config.get_settings.cache_clear()
    storage._storage = None
