"""Build a LABELED, AI-GENERATED dataset of mud-wall damage (task C4, plan section 9.1).

EVERYTHING this script writes is generated. None of it is a real wall, and a model
trained or scored on it says nothing about real At-Turaif walls (see docs/AI_DATASET.md).

Method (inpainting, so the mask we draw IS the label):
  1. Ask the image model for an intact mud wall ("base wall"). Only text prompts go to
     the service. No real photo is ever sent.
  2. Draw a damage mask in code (crack, plaster loss, moisture, material loss, edge erosion).
  3. Paint the mask solid green on a copy of the base wall and ask the model to replace
     ONLY the green area with that damage.
  4. Composite: pixels outside the mask are copied back from the base wall, so the label
     is exact by construction. Reject results that changed nothing inside the mask, that
     rebuilt a different scene, or that left the green marker behind.
  5. Write image + label + sidecar JSON (source, model, prompt, date) for every image.
     Test images are held out by BASE WALL, never by image.

Usage (run on a machine that can reach the API; the key is read from GEMINI_API_KEY):
  python scripts/generate_ai_dataset.py --dry-run
  python scripts/generate_ai_dataset.py --n-bases 1 --per-base 1 --types crack   # smoke test
  python scripts/generate_ai_dataset.py --n-bases 10 --per-base 5                # pilot, 50 images
  python scripts/generate_ai_dataset.py --contact-sheet                          # sheets for expert review
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.models.enums import DAMAGE_COLORS, DamageType  # noqa: E402
from app.vision.imageio import decode_image  # noqa: E402
from app.vision.synthetic import LABEL_TO_DAMAGE  # noqa: E402

W, H = 1024, 768
DAMAGE_TO_LABEL = {d: i for i, d in LABEL_TO_DAMAGE.items()}
ALL_TYPES = [LABEL_TO_DAMAGE[i] for i in sorted(LABEL_TO_DAMAGE)]
DEFAULT_MODEL = "gemini-3.1-flash-image"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "sample_data" / "generated"
MARKER_BGR = (0, 255, 0)

BASE_PROMPT = (
    "Photograph of an intact, weathered adobe (mud-brick) wall of traditional Najdi architecture "
    "in Saudi Arabia, plain clay-colored mud plaster with natural texture and no damage. Straight-on "
    "view, even soft daylight. The top edge of the wall is visible with a band of plain clear sky above it. "
    "No people, no text, no vegetation, no signs."
)
BASE_VARIANTS = [
    "warm sand-colored plaster, morning light",
    "slightly darker brown plaster, overcast sky",
    "pale beige plaster, bright midday diffuse light",
    "reddish clay plaster, late afternoon soft light",
]
DAMAGE_PROMPTS = {
    DamageType.CRACK: "a realistic thin irregular crack in the mud plaster with fine hairline branches",
    DamageType.PLASTER_LOSS: (
        "an area where the outer mud plaster has flaked off, exposing the rougher mud-brick layer "
        "underneath, with uneven edges"
    ),
    DamageType.MOISTURE_EROSION: (
        "moisture damage: darker damp staining and a softened, eroded, crumbling mud surface"
    ),
    DamageType.MATERIAL_LOSS: (
        "missing wall material: a shallow cavity where mud and bricks have fallen out, with rough crumbling edges"
    ),
    DamageType.EDGE_EROSION: (
        "eroded, rounded and crumbled top edge of the wall where weathering has worn away the outline; "
        "the sky stays plain sky"
    ),
}
EDIT_TEMPLATE = (
    "In this photograph, the area painted solid bright green marks a region. Replace ONLY that green "
    "region with {damage}, blending naturally with the surrounding wall. Do not change anything outside "
    "the green region. Do not leave any green in the result."
)


@dataclass
class Thresholds:
    """Experimental acceptance limits. They are NOT calibrated: read them from the pilot logs and adjust."""

    min_inside_diff: float = 8.0  # mean abs change (0-255) inside the mask; below it the model changed nothing
    max_outside_diff: float = 25.0  # mean abs change outside the mask; above it the model rebuilt another scene
    max_green_fraction: float = 0.005  # share of mask pixels still marker-green
    min_area: float = 0.002  # mask area as a fraction of the image
    max_area: float = 0.35


class GenerationError(RuntimeError):
    pass


class MissingApiKey(RuntimeError):
    pass


class ImageGenerator(Protocol):
    model: str

    def generate_base(self, prompt: str) -> np.ndarray: ...

    def edit(self, image_bgr: np.ndarray, prompt: str) -> np.ndarray: ...


class GeminiGenerator:
    """Calls the Gemini API (google-genai SDK). Needs GEMINI_API_KEY and requirements-generate.txt."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise MissingApiKey("لم أجد مفتاح GEMINI_API_KEY. اضبطه في نفس نافذة Terminal قبل التشغيل.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:  # pragma: no cover - depends on the machine
            raise RuntimeError("ثبّت المكتبة أولًا: pip install -r requirements-generate.txt") from e
        self._types = types
        self._client = genai.Client(api_key=key)
        self.model = model

    def _call(self, contents: list) -> np.ndarray:  # pragma: no cover - needs network and a key
        resp = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=self._types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        for cand in resp.candidates or []:
            for part in (cand.content.parts if cand.content else None) or []:
                inline = getattr(part, "inline_data", None)
                if inline is not None and inline.data:
                    return decode_image(inline.data)
        raise GenerationError("لم يُرجع النموذج صورة (ربما رفض الطلب لأسباب أمان أو الحصة).")

    def generate_base(self, prompt: str) -> np.ndarray:  # pragma: no cover
        return self._call([prompt])

    def edit(self, image_bgr: np.ndarray, prompt: str) -> np.ndarray:  # pragma: no cover
        from PIL import Image

        pil = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
        return self._call([prompt, pil])


# ---------------------------------------------------------------- geometry


def fit_4_3(img: np.ndarray, size: tuple[int, int] = (W, H)) -> np.ndarray:
    """Center-crop to 4:3 then resize, so nothing is stretched."""
    h, w = img.shape[:2]
    target = size[0] / size[1]
    if w / h > target:
        new_w = int(round(h * target))
        x0 = (w - new_w) // 2
        img = img[:, x0 : x0 + new_w]
    else:
        new_h = int(round(w / target))
        y0 = (h - new_h) // 2
        img = img[y0 : y0 + new_h]
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA)


def find_top_edge(img: np.ndarray) -> np.ndarray | None:
    """Per-column row of the wall's top edge (sky above, clay below), or None if no clear edge."""
    h, w = img.shape[:2]
    b, r = img[..., 0].astype(np.int16), img[..., 2].astype(np.int16)
    wall = (r - b) > 15  # clay is red-dominant, sky is blue/white-dominant
    top = np.full(w, -1, np.int32)
    for x in range(w):
        col = np.flatnonzero(wall[: int(h * 0.6), x])
        if len(col):
            top[x] = col[0]
    valid = top >= 0
    if valid.mean() < 0.8:
        return None
    top = np.where(valid, top, int(np.median(top[valid]))).astype(np.float32)
    k = 31
    smooth = np.convolve(np.pad(top, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
    if not (0.03 * h < np.median(smooth) < 0.4 * h):
        return None
    return smooth.astype(np.int32)


def _blob(rng, cx, cy, rx, ry, rough=0.3, pts=20) -> np.ndarray:
    ang = np.sort(rng.uniform(0, 2 * np.pi, pts))
    r = 1 + rng.uniform(-rough, rough, pts)
    poly = np.stack([cx + rx * r * np.cos(ang), cy + ry * r * np.sin(ang)], 1).astype(np.int32)
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [poly], 255)
    return m


def _crack(rng, wall_top: int) -> np.ndarray:
    m = np.zeros((H, W), np.uint8)

    def walk(x, y, steps, heading):
        pts = [(x, y)]
        for _ in range(steps):
            heading += rng.normal(0, 0.35)
            x += np.cos(heading) * rng.uniform(12, 20)
            y += np.sin(heading) * rng.uniform(12, 20)
            if not (0 <= x < W and wall_top <= y < H):
                break
            pts.append((int(x), int(y)))
        return pts

    x0 = rng.uniform(0.2, 0.8) * W
    y0 = rng.uniform(wall_top + 10, wall_top + 0.3 * (H - wall_top))
    main = walk(x0, y0, int(rng.integers(30, 60)), np.pi / 2 + rng.normal(0, 0.25))
    cv2.polylines(m, [np.array(main, np.int32)], False, 255, int(rng.integers(4, 8)))
    for _ in range(int(rng.integers(0, 3))):
        if len(main) < 6:
            break
        sx, sy = main[int(rng.integers(2, len(main) - 2))]
        br = walk(sx, sy, int(rng.integers(6, 16)), np.pi / 2 + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1))
        if len(br) > 1:
            cv2.polylines(m, [np.array(br, np.int32)], False, 255, 3)
    return cv2.dilate(m, np.ones((3, 3), np.uint8))


def draw_mask(kind: DamageType, rng, edge_rows: np.ndarray | None = None) -> np.ndarray | None:
    """Binary uint8 mask (0/255) for one damage region, drawn entirely by code.

    Returns None only for edge erosion when the wall has no detectable top edge."""
    wall_top = int(np.percentile(edge_rows, 90)) + 25 if edge_rows is not None else int(0.25 * H)
    span = H - wall_top
    if kind is DamageType.CRACK:
        return _crack(rng, wall_top)
    if kind is DamageType.PLASTER_LOSS:
        m = np.zeros((H, W), np.uint8)
        for _ in range(int(rng.integers(1, 4))):
            cx, cy = rng.uniform(0.15, 0.85) * W, wall_top + rng.uniform(0.15, 0.7) * span
            m |= _blob(rng, cx, cy, rng.uniform(60, 130), rng.uniform(50, 100))
        return m
    if kind is DamageType.MOISTURE_EROSION:
        m = np.zeros((H, W), np.uint8)
        for _ in range(int(rng.integers(1, 3))):
            cx, cy = rng.uniform(0.2, 0.8) * W, H - rng.uniform(0.08, 0.22) * span
            m |= _blob(rng, cx, cy, rng.uniform(120, 260), rng.uniform(50, 110), rough=0.35)
        return m
    if kind is DamageType.MATERIAL_LOSS:
        cx, cy = rng.uniform(0.2, 0.8) * W, wall_top + rng.uniform(0.2, 0.75) * span
        m = _blob(rng, cx, cy, rng.uniform(50, 110), rng.uniform(40, 90), rough=0.4)
        for _ in range(int(rng.integers(0, 3))):
            m |= _blob(rng, cx + rng.uniform(-150, 150), cy + rng.uniform(-100, 100), rng.uniform(10, 30), rng.uniform(10, 30))
        return m
    if kind is DamageType.EDGE_EROSION:
        if edge_rows is None:
            return None
        seg = int(rng.uniform(150, 400))
        x0 = int(rng.uniform(0.05, 0.95) * (W - seg))
        depth = np.clip(np.cumsum(rng.normal(0, 3, seg)) + rng.uniform(30, 60), 25, 80)
        m = np.zeros((H, W), np.uint8)
        for i in range(seg):
            y = int(edge_rows[x0 + i])
            m[max(0, y - 22) : min(H, y + int(depth[i])), x0 + i] = 255
        return m
    raise ValueError(kind)


# ---------------------------------------------------------------- compositing and checks


def paint_marker(base: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = base.copy()
    out[mask > 0] = MARKER_BGR
    return out


def composite(base: np.ndarray, generated: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Outside the mask: the base wall, byte for byte. Inside: the generated pixels,
    softened over a few pixels but never beyond the mask edge."""
    soft = cv2.GaussianBlur(mask, (0, 0), 2).astype(np.float32) / 255.0
    soft = np.minimum(soft, mask.astype(np.float32) / 255.0)[..., None]
    out = base.astype(np.float32) * (1 - soft) + generated.astype(np.float32) * soft
    out = np.clip(out, 0, 255).astype(np.uint8)
    out[mask == 0] = base[mask == 0]
    return out


def verify(base: np.ndarray, generated: np.ndarray, mask: np.ndarray, th: Thresholds) -> tuple[bool, str, dict]:
    inside, outside = mask > 0, mask == 0
    diff = np.abs(generated.astype(np.int16) - base.astype(np.int16)).mean(axis=2)
    green = (generated[..., 1] > 200) & (generated[..., 0] < 80) & (generated[..., 2] < 80)
    stats = {
        "inside_diff": round(float(diff[inside].mean()), 2),
        "outside_diff": round(float(diff[outside].mean()), 2),
        "green_fraction": round(float(green[inside].mean()), 4),
        "mask_area_fraction": round(float(inside.mean()), 4),
    }
    if not th.min_area <= stats["mask_area_fraction"] <= th.max_area:
        return False, "mask_area_out_of_range", stats
    if stats["green_fraction"] > th.max_green_fraction:
        return False, "marker_left_behind", stats
    if stats["inside_diff"] < th.min_inside_diff:
        return False, "no_change_inside_mask", stats
    if stats["outside_diff"] > th.max_outside_diff:
        return False, "scene_rebuilt_outside_mask", stats
    return True, "ok", stats


def assign_splits(base_ids: list[str], test_fraction: float = 0.2, seed: int = 0) -> dict[str, str]:
    """Hold out whole base walls: every image made from a test base is a test image."""
    ids = sorted(base_ids)
    n_test = max(1, round(len(ids) * test_fraction)) if len(ids) >= 2 else 0
    order = np.random.default_rng(seed).permutation(len(ids))
    test = {ids[i] for i in order[:n_test]}
    return {b: ("test" if b in test else "train") for b in ids}


# ---------------------------------------------------------------- pipeline


def plan_calls(n_bases: int, per_base: int) -> int:
    return n_bases + n_bases * per_base


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(
    gen: ImageGenerator,
    out: Path,
    n_bases: int,
    per_base: int,
    types: list[DamageType],
    seed: int = 0,
    max_calls: int = 100,
    th: Thresholds | None = None,
    max_consecutive_errors: int = 3,
) -> dict:
    th = th or Thresholds()
    if plan_calls(n_bases, per_base) > max_calls:
        raise ValueError(f"الخطة تحتاج {plan_calls(n_bases, per_base)} طلبًا والحد المسموح {max_calls}. ارفع --max-calls عمدًا.")
    for sub in ("bases", "images", "labels", "meta"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    base_ids = [f"base{i + 1:03d}" for i in range(n_bases)]
    splits = assign_splits(base_ids, seed=seed)
    accepted: list[dict] = []
    rejected: list[dict] = []
    calls = errors = 0

    def reject(base_id, kind, reason, stats=None):
        rejected.append({"base": base_id, "damage_type": kind.value if kind else None, "reason": reason, **(stats or {})})

    for bi, base_id in enumerate(base_ids):
        variant = BASE_VARIANTS[bi % len(BASE_VARIANTS)]
        base_prompt = f"{BASE_PROMPT} Style: {variant}."
        try:
            calls += 1
            base = fit_4_3(gen.generate_base(base_prompt))
            errors = 0
        except Exception as e:  # noqa: BLE001 - any service failure is logged, the run goes on
            errors += 1
            reject(base_id, None, f"generator_error: {e}")
            if errors >= max_consecutive_errors:
                break
            continue
        cv2.imwrite(str(out / "bases" / f"gen_{base_id}.jpg"), base, [cv2.IMWRITE_JPEG_QUALITY, 92])
        edge_rows = find_top_edge(base)
        for k in range(per_base):
            kind = types[(bi * per_base + k) % len(types)]
            mask = None
            for _ in range(5):
                mask = draw_mask(kind, rng, edge_rows)
                if mask is None or th.min_area <= (mask > 0).mean() <= th.max_area:
                    break
            if mask is None:
                reject(base_id, kind, "no_top_edge_found")
                continue
            prompt = EDIT_TEMPLATE.format(damage=DAMAGE_PROMPTS[kind])
            try:
                calls += 1
                generated = fit_4_3(gen.edit(paint_marker(base, mask), prompt))
                errors = 0
            except Exception as e:  # noqa: BLE001
                errors += 1
                reject(base_id, kind, f"generator_error: {e}")
                if errors >= max_consecutive_errors:
                    break
                continue
            ok, reason, stats = verify(base, generated, mask, th)
            if not ok:
                reject(base_id, kind, reason, stats)
                continue
            name = f"gen_{base_id}_{kind.value}_{k + 1:02d}"
            label = np.where(mask > 0, DAMAGE_TO_LABEL[kind], 0).astype(np.uint8)
            cv2.imwrite(str(out / "images" / f"{name}.jpg"), composite(base, generated, mask), [cv2.IMWRITE_JPEG_QUALITY, 92])
            cv2.imwrite(str(out / "labels" / f"{name}.png"), label)
            meta = {
                "source": "generated",
                "name": name,
                "generated_by": gen.model,
                "date": _now(),
                "base_id": base_id,
                "base_prompt": base_prompt,
                "edit_prompt": prompt,
                "damage_type": kind.value,
                "label_id": DAMAGE_TO_LABEL[kind],
                "split": splits[base_id],
                "mask_seed": seed,
                "checks": stats,
                "thresholds": th.__dict__,
                "expert_review": "unreviewed",
                "note": "AI-generated image. Not a real wall. Do not report scores on it as accuracy on At-Turaif.",
            }
            (out / "meta" / f"{name}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            accepted.append(meta)
        if errors >= max_consecutive_errors:
            break
    summary = {
        "source": "generated",
        "model": gen.model,
        "date": _now(),
        "calls": calls,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "by_type": {t.value: sum(a["damage_type"] == t.value for a in accepted) for t in types},
        "by_split": {s: sum(a["split"] == s for a in accepted) for s in ("train", "test")},
        "rejected_reasons": {r: sum(x["reason"].split(":")[0] == r for x in rejected) for r in {x["reason"].split(":")[0] for x in rejected}},
        "note": "Generated data only. Not real walls.",
    }
    (out / "manifest.jsonl").write_text("\n".join(json.dumps(a, ensure_ascii=False) for a in accepted), encoding="utf-8")
    (out / "rejected.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rejected), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


# ---------------------------------------------------------------- expert review sheets


def contact_sheets(out: Path, n: int = 50, per_page: int = 12, cols: int = 4, seed: int = 0) -> list[Path]:
    """Random sample of accepted images with the label outlined, 12 per page, plus a CSV to fill in."""
    rows = [json.loads(line) for line in (out / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    pick = [rows[i] for i in np.random.default_rng(seed).permutation(len(rows))[:n]]
    (out / "review").mkdir(exist_ok=True)
    tw, th_ = 480, 360
    pages = []
    for p in range(0, len(pick), per_page):
        chunk = pick[p : p + per_page]
        n_rows = (len(chunk) + cols - 1) // cols
        sheet = np.full((n_rows * (th_ + 28), cols * tw, 3), 255, np.uint8)
        for i, meta in enumerate(chunk):
            img = cv2.imread(str(out / "images" / f"{meta['name']}.jpg"))
            lab = cv2.imread(str(out / "labels" / f"{meta['name']}.png"), cv2.IMREAD_GRAYSCALE)
            cnts, _ = cv2.findContours((lab > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            hexcol = DAMAGE_COLORS[DamageType(meta["damage_type"])].lstrip("#")
            rgb = tuple(int(hexcol[j : j + 2], 16) for j in (0, 2, 4))
            cv2.drawContours(img, cnts, -1, rgb[::-1], 3)
            tile = cv2.resize(img, (tw, th_), interpolation=cv2.INTER_AREA)
            y, x = (i // cols) * (th_ + 28), (i % cols) * tw
            sheet[y : y + th_, x : x + tw] = tile
            cv2.putText(sheet, f"{meta['name']} [{meta['split']}]", (x + 4, y + th_ + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        path = out / "review" / f"sheet_{p // per_page + 1:02d}.jpg"
        cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
        pages.append(path)
    with (out / "review" / "review.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "damage_type", "realistic (yes/no)", "notes"])
        for meta in pick:
            w.writerow([meta["name"], meta["damage_type"], "", ""])
    return pages


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n-bases", type=int, default=10, help="عدد جدران الأساس السليمة")
    ap.add_argument("--per-base", type=int, default=5, help="عدد الصور المولّدة لكل جدار أساس")
    ap.add_argument("--types", nargs="*", default=[t.value for t in ALL_TYPES], choices=[t.value for t in ALL_TYPES])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default=os.environ.get("HCC_GEMINI_MODEL", DEFAULT_MODEL))
    ap.add_argument("--max-calls", type=int, default=60, help="سقف الطلبات للخدمة (حماية من التكلفة)")
    ap.add_argument("--price-per-image", type=float, default=None, help="سعر الصورة بالدولار من صفحة التسعير، لحساب تقدير التكلفة")
    ap.add_argument("--dry-run", action="store_true", help="يطبع الخطة والتكلفة التقديرية دون أي اتصال")
    ap.add_argument("--contact-sheet", action="store_true", help="يصنع صفحات مراجعة للمختص من الصور المقبولة")
    args = ap.parse_args(argv)

    if args.contact_sheet:
        pages = contact_sheets(args.out)
        print(f"كتبت {len(pages)} صفحة مراجعة في {args.out / 'review'} مع review.csv لتعبئته.")
        return 0

    calls = plan_calls(args.n_bases, args.per_base)
    print(f"الخطة: {args.n_bases} جدار أساس × {args.per_base} = {args.n_bases * args.per_base} صورة تلف. عدد الطلبات للخدمة: {calls}.")
    if args.price_per_image is not None:
        print(f"تقدير التكلفة: {calls} × {args.price_per_image} = {calls * args.price_per_image:.2f} دولارًا (بدون رموز الإدخال). السعر من إدخالك أنت.")
    print("لا تُرسل أي صورة حقيقية. يُرسل نص البرومبت وصور مولّدة فقط.")
    if args.dry_run:
        return 0
    if calls > args.max_calls:
        print(f"الخطة ({calls}) أكبر من --max-calls ({args.max_calls}). ارفعه عمدًا إن أردت.")
        return 2
    try:
        gen = GeminiGenerator(args.model)
    except (MissingApiKey, RuntimeError) as e:
        print(e)
        return 2
    summary = run(gen, args.out, args.n_bases, args.per_base, [DamageType(t) for t in args.types], args.seed, args.max_calls)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("هذه صور مولّدة وليست جدرانًا حقيقية. راجع الرفض في rejected.jsonl ثم صفحات المراجعة (--contact-sheet).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
