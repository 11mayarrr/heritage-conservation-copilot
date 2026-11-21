"""C4 pipeline tests. No network and no API key: a fake generator stands in for the service."""
import json

import cv2
import numpy as np
import pytest

import generate_ai_dataset as g
from app.models.enums import DamageType


def clay_wall(seed=0, sky_frac=0.2):
    """A synthetic stand-in 'base wall': blue sky band on top, clay below (BGR)."""
    rng = np.random.default_rng(seed)
    img = np.zeros((g.H, g.W, 3), np.uint8)
    sky = int(g.H * sky_frac)
    img[:sky] = (235, 200, 150)  # sky: blue-dominant
    img[sky:] = (110, 150, 190)  # clay: red-dominant
    noise = rng.normal(0, 4, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


class FakeGenerator:
    """Test double. Returns a wall, then 'damage': whatever is green becomes dark brown."""

    model = "fake-test-model"

    def __init__(self, mode="ok"):
        self.mode, self.calls = mode, 0

    def generate_base(self, prompt):
        self.calls += 1
        self._base = clay_wall(self.calls)
        return self._base

    def edit(self, image_bgr, prompt):
        self.calls += 1
        out = image_bgr.copy()
        green = (image_bgr == np.array(g.MARKER_BGR)).all(axis=2)
        if self.mode == "ok":
            out[green] = (40, 60, 90)
        elif self.mode == "nothing":
            out[green] = self._base[green]  # gives back the untouched wall
        elif self.mode == "marker":
            pass  # leaves the green marker in place
        elif self.mode == "rebuilt":
            out = 255 - out  # whole scene changed
        elif self.mode == "error":
            raise RuntimeError("quota exceeded")
        return out


# ---------------------------------------------------------------- masks


@pytest.mark.parametrize("kind", g.ALL_TYPES)
def test_every_damage_type_has_a_plausible_mask(kind):
    base = clay_wall()
    edge = g.find_top_edge(base)
    m = g.draw_mask(kind, np.random.default_rng(1), edge)
    assert m.shape == (g.H, g.W) and m.dtype == np.uint8
    assert set(np.unique(m)) <= {0, 255}
    area = (m > 0).mean()
    assert g.Thresholds().min_area <= area <= g.Thresholds().max_area, (kind, area)


def test_masks_are_deterministic_for_a_seed():
    edge = g.find_top_edge(clay_wall())
    a = g.draw_mask(DamageType.CRACK, np.random.default_rng(7), edge)
    b = g.draw_mask(DamageType.CRACK, np.random.default_rng(7), edge)
    assert np.array_equal(a, b)


def test_top_edge_is_found_near_the_sky_boundary():
    edge = g.find_top_edge(clay_wall(sky_frac=0.2))
    assert edge is not None
    assert abs(float(np.median(edge)) - 0.2 * g.H) < 12


def test_no_edge_when_there_is_no_sky():
    all_clay = np.full((g.H, g.W, 3), (110, 150, 190), np.uint8)
    assert g.find_top_edge(all_clay) is None
    assert g.draw_mask(DamageType.EDGE_EROSION, np.random.default_rng(0), None) is None


def test_non_edge_damage_stays_below_the_sky():
    base = clay_wall(sky_frac=0.2)
    edge = g.find_top_edge(base)
    for kind in (DamageType.CRACK, DamageType.PLASTER_LOSS, DamageType.MATERIAL_LOSS):
        for s in range(5):
            m = g.draw_mask(kind, np.random.default_rng(s), edge)
            rows = np.flatnonzero(m.any(axis=1))
            assert rows.min() >= 0.2 * g.H, (kind, s)


# ---------------------------------------------------------------- compositing and verification


def test_composite_leaves_everything_outside_the_mask_untouched():
    base = clay_wall()
    mask = g.draw_mask(DamageType.PLASTER_LOSS, np.random.default_rng(2), g.find_top_edge(base))
    generated = 255 - base
    out = g.composite(base, generated, mask)
    assert np.array_equal(out[mask == 0], base[mask == 0])
    assert not np.array_equal(out[mask > 0], base[mask > 0])


def test_verify_accepts_a_real_change_inside_the_mask():
    base = clay_wall()
    mask = g.draw_mask(DamageType.PLASTER_LOSS, np.random.default_rng(2), g.find_top_edge(base))
    generated = base.copy()
    generated[mask > 0] = (40, 60, 90)
    ok, reason, stats = g.verify(base, generated, mask, g.Thresholds())
    assert ok and reason == "ok", stats


@pytest.mark.parametrize("mode,expected", [
    ("nothing", "no_change_inside_mask"),
    ("marker", "marker_left_behind"),
    ("rebuilt", "scene_rebuilt_outside_mask"),
])
def test_verify_rejects_bad_generations(mode, expected):
    base = clay_wall()
    mask = g.draw_mask(DamageType.PLASTER_LOSS, np.random.default_rng(2), g.find_top_edge(base))
    gen = FakeGenerator(mode)
    gen._base = base
    generated = gen.edit(g.paint_marker(base, mask), "x")
    ok, reason, _ = g.verify(base, generated, mask, g.Thresholds())
    assert not ok and reason == expected


# ---------------------------------------------------------------- splits


def test_splits_hold_out_whole_base_walls_and_are_deterministic():
    ids = [f"base{i:03d}" for i in range(1, 11)]
    s = g.assign_splits(ids, 0.2, seed=3)
    assert s == g.assign_splits(ids, 0.2, seed=3)
    assert sorted(set(s.values())) == ["test", "train"]
    assert sum(v == "test" for v in s.values()) == 2


def test_single_base_has_no_test_split():
    assert g.assign_splits(["base001"]) == {"base001": "train"}


# ---------------------------------------------------------------- pipeline


def test_pipeline_labels_everything_as_generated(tmp_path):
    gen = FakeGenerator()
    summary = g.run(gen, tmp_path, n_bases=4, per_base=5, types=g.ALL_TYPES, seed=1, max_calls=100)
    assert summary["accepted"] == 20 and summary["rejected"] == 0
    assert gen.calls == g.plan_calls(4, 5)
    manifest = [json.loads(l) for l in (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(manifest) == 20
    for meta in manifest:
        assert meta["source"] == "generated"
        assert meta["generated_by"] == "fake-test-model"
        assert meta["name"].startswith("gen_")
        assert meta["edit_prompt"] and meta["date"] and meta["expert_review"] == "unreviewed"
        assert (tmp_path / "images" / f"{meta['name']}.jpg").exists()
        label = cv2.imread(str(tmp_path / "labels" / f"{meta['name']}.png"), cv2.IMREAD_GRAYSCALE)
        assert set(np.unique(label)) == {0, meta["label_id"]}


def test_pipeline_never_mixes_a_base_wall_across_splits(tmp_path):
    g.run(FakeGenerator(), tmp_path, n_bases=6, per_base=5, types=g.ALL_TYPES, seed=2, max_calls=100)
    manifest = [json.loads(l) for l in (tmp_path / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    seen: dict[str, str] = {}
    for meta in manifest:
        assert seen.setdefault(meta["base_id"], meta["split"]) == meta["split"]
    assert {"train", "test"} <= set(seen.values())


def test_pipeline_logs_rejections_and_writes_nothing_for_them(tmp_path):
    summary = g.run(FakeGenerator("nothing"), tmp_path, n_bases=2, per_base=5, types=g.ALL_TYPES, max_calls=100)
    assert summary["accepted"] == 0 and summary["rejected"] == 10
    assert summary["rejected_reasons"] == {"no_change_inside_mask": 10}
    assert list((tmp_path / "images").glob("*")) == []


def test_pipeline_refuses_a_plan_above_the_call_cap(tmp_path):
    with pytest.raises(ValueError):
        g.run(FakeGenerator(), tmp_path, n_bases=10, per_base=5, types=g.ALL_TYPES, max_calls=30)
    assert not (tmp_path / "images").exists()


def test_pipeline_stops_after_repeated_service_errors(tmp_path):
    gen = FakeGenerator("error")
    summary = g.run(gen, tmp_path, n_bases=5, per_base=5, types=g.ALL_TYPES, max_calls=100)
    assert summary["accepted"] == 0
    assert gen.calls <= 1 + 3  # one base wall, then stops after 3 consecutive errors


def test_edge_erosion_is_skipped_when_the_base_has_no_top_edge(tmp_path):
    class NoSky(FakeGenerator):
        def generate_base(self, prompt):
            self.calls += 1
            return np.full((g.H, g.W, 3), (110, 150, 190), np.uint8)

    summary = g.run(NoSky(), tmp_path, n_bases=1, per_base=1, types=[DamageType.EDGE_EROSION], max_calls=10)
    assert summary["accepted"] == 0 and summary["rejected_reasons"] == {"no_top_edge_found": 1}


# ---------------------------------------------------------------- safety, CLI, review sheets


def test_gemini_generator_needs_a_key_and_never_calls_out_without_one(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(g.MissingApiKey):
        g.GeminiGenerator()


def test_dry_run_makes_no_calls_and_prints_the_plan(capsys, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert g.main(["--dry-run", "--n-bases", "10", "--per-base", "5", "--price-per-image", "0.1"]) == 0
    out = capsys.readouterr().out
    assert "60" in out and "6.00" in out and "لا تُرسل أي صورة حقيقية" in out


def test_cli_refuses_without_key(capsys, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert g.main(["--n-bases", "1", "--per-base", "1"]) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().out


def test_cli_refuses_a_plan_above_the_cap(capsys, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    assert g.main(["--n-bases", "50", "--per-base", "5", "--max-calls", "60"]) == 2


def test_contact_sheets_are_written_for_expert_review(tmp_path):
    g.run(FakeGenerator(), tmp_path, n_bases=3, per_base=5, types=g.ALL_TYPES, max_calls=100)
    pages = g.contact_sheets(tmp_path, n=15, per_page=12)
    assert len(pages) == 2 and all(p.exists() for p in pages)
    assert (tmp_path / "review" / "review.csv").read_text(encoding="utf-8").count("\n") == 16


# ---------------------------------------------------------------- docs stay in sync with the code

from pathlib import Path  # noqa: E402

DOC = (Path(__file__).resolve().parents[1] / "docs" / "AI_DATASET.md").read_text(encoding="utf-8")


def test_doc_says_the_data_is_generated_and_not_real():
    assert "صور مولّدة، وليست جدرانًا حقيقية" in DOC
    assert "gen_" in DOC


def test_doc_lists_every_rejection_reason_the_code_can_produce(tmp_path):
    reasons = {"no_change_inside_mask", "marker_left_behind", "scene_rebuilt_outside_mask",
               "mask_area_out_of_range", "no_top_edge_found"}
    for r in reasons:
        assert r in DOC, r
    import inspect
    src = inspect.getsource(g)
    for r in reasons:
        assert f'"{r}"' in src, r


def test_doc_label_ids_match_the_system_labels():
    for label_id, damage in g.LABEL_TO_DAMAGE.items():
        assert g.DAMAGE_TO_LABEL[damage] == label_id
    assert "1 تشقق" in DOC and "5 تآكل حافة" in DOC


def test_generated_output_is_gitignored_and_requirements_are_separate():
    root = Path(__file__).resolve().parents[1]
    assert "sample_data/generated/" in (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "google-genai" in (root / "requirements-generate.txt").read_text(encoding="utf-8")
    assert "google-genai" not in (root / "requirements.txt").read_text(encoding="utf-8")
