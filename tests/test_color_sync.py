"""The atlas colors are defined twice (backend render + frontend editor); keep them identical."""
import re
from pathlib import Path

from app.models.enums import DAMAGE_COLORS


def test_frontend_colors_match_backend():
    ts = (Path(__file__).resolve().parents[1] / "frontend/src/lib/constants.ts").read_text(encoding="utf-8")
    for dtype, color in DAMAGE_COLORS.items():
        m = re.search(rf"{dtype.value}:\s*\{{[^}}]*color:\s*\"(#[0-9A-Fa-f]{{6}})\"", ts)
        assert m, dtype
        assert m.group(1).upper() == color.upper(), dtype
