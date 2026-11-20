"""Per-wall reference grid (الشبكة المرجعية لكل جدار).

The challenge action map asks for a reference grid defined for each wall, so a
location such as "C2" means the same spot on that wall in every inspection.

* A wall may store its own grid (columns, rows, and optionally the real wall
  width/height in metres).
* A wall without one falls back to the temporary default grid from settings
  (HCC_GRID_COLS x HCC_GRID_ROWS), marked type="temporary".
* Every inspection keeps a frozen copy of the grid it was analysed with, so
  approved cases never change silently when the wall grid is edited later.

Real dimensions only give an *estimated* area in m^2, valid when the photo is
framed to the full wall face and taken roughly straight-on. The UI and report
say so wherever the value appears.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings

MAX_COLS = 26  # columns are lettered A..Z
MAX_ROWS = 30


def default_grid() -> dict[str, Any]:
    s = get_settings()
    return {"cols": s.grid_cols, "rows": s.grid_rows, "width_m": None, "height_m": None,
            "note": "", "type": "temporary", "version": 0}


def normalize(data: dict[str, Any], version: int) -> dict[str, Any]:
    """Validated wall grid as stored on the wall."""
    w, h = data.get("width_m"), data.get("height_m")
    if (w is None) != (h is None):
        raise ValueError("أدخل العرض والارتفاع معًا، أو اتركهما فارغين.")
    return {
        "cols": int(data["cols"]),
        "rows": int(data["rows"]),
        "width_m": float(w) if w is not None else None,
        "height_m": float(h) if h is not None else None,
        "note": (data.get("note") or "").strip(),
        "type": "wall",
        "version": version,
    }


def wall_grid(wall) -> dict[str, Any]:
    """Effective grid for a wall: its own if defined, otherwise the temporary default."""
    return dict(wall.grid) if wall.grid else default_grid()


def dims(grid: dict | None) -> tuple[int, int]:
    s = get_settings()
    g = grid or {}
    return int(g.get("cols") or s.grid_cols), int(g.get("rows") or s.grid_rows)


def area_m2(area_fraction: float, grid: dict | None) -> float | None:
    """Estimated area in m^2, only when the grid carries real wall dimensions."""
    g = grid or {}
    if g.get("width_m") and g.get("height_m"):
        return round(area_fraction * g["width_m"] * g["height_m"], 3)
    return None


def cell_size_m(grid: dict | None) -> tuple[float, float] | None:
    g = grid or {}
    if g.get("width_m") and g.get("height_m"):
        cols, rows = dims(g)
        return round(g["width_m"] / cols, 3), round(g["height_m"] / rows, 3)
    return None
