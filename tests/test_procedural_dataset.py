"""C4 (code-only path), C5 and C6 tests. Small datasets are drawn into tmp folders; nothing is downloaded."""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

import eval_on_dataset as ev
import generate_procedural_dataset as gp
import train_on_dataset as tr
from app.vision.detectors.pixel_model import SyntheticPixelDetector
from app.vision.synthetic import LABEL_TO_DAMAGE, MIN_FOCUS_PIXELS, make_labeled, make_labeled_varied

ROOT = Path(__file__).resolve().parents[1]
EVAL = json.loads((ROOT / "docs" / "EVALUATION_GENERATED.json").read_text(encoding="utf-8"))
EVAL_MD = (ROOT / "docs" / "EVALUATION_GENERATED.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    out = tmp_path_factory.mktemp("proc")
    gp.build(out, per_type=5)
    return out


# ---------------------------------------------------------------- generator


@pytest.mark.parametrize("focus", sorted(LABEL_TO_DAMAGE))
def test_focus_type_always_appears_with_real_area(focus):
    for s in range(3):
        _, lab, _ = make_labeled_varied(s, focus)
        assert (lab == focus).mean() >= MIN_FOCUS_PIXELS


def test_varied_is_deterministic_and_photometry_never_changes_labels():
    a, la, ua = make_labeled_varied(4, 2)
    b, lb, ub = make_labeled_varied(4, 2)
    assert np.array_equal(a, b) and np.array_equal(la, lb) and ua == ub
    _, label_only = make_labeled(ua)
    assert np.array_equal(la, label_only)


def test_bad_focus_is_rejected():
    with pytest.raises(ValueError):
        make_labeled_varied(0, 9)


# ---------------------------------------------------------------- dataset on disk


def test_dataset_is_balanced_labeled_and_marked_generated(tiny):
    rows = [json.loads(l) for l in (tiny / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 25
    for d in LABEL_TO_DAMAGE.values():
        assert sum(r["focus_damage_type"] == d.value for r in rows) == 5
    for r in rows:
        assert r["source"] == "generated" and r["name"].startswith("gen_proc_") and r["prompt"] is None
        lab = cv2.imread(str(tiny / "labels" / f"{r['name']}.png"), cv2.IMREAD_GRAYSCALE)
        assert lab.shape == (480, 640) and int(lab.max()) <= 5
        assert (tiny / "images" / f"{r['name']}.jpg").exists()
    assert json.loads((tiny / "summary.json").read_text(encoding="utf-8"))["by_split"] == {"train": 20, "test": 5}


def test_every_type_has_test_images_and_split_is_stable():
    assert [gp.split_of(i) for i in range(10)] == ["train"] * 4 + ["test"] + ["train"] * 4 + ["test"]


def test_generation_is_repeatable(tmp_path):
    gp.build(tmp_path, per_type=1)
    again = tmp_path.parent / (tmp_path.name + "_b")
    gp.build(again, per_type=1)
    for f in sorted((tmp_path / "images").iterdir()):
        assert (again / "images" / f.name).read_bytes() == f.read_bytes()


# ---------------------------------------------------------------- C5 training


def test_training_uses_only_train_rows_and_writes_a_log(tiny, tmp_path):
    out = tmp_path / "w.joblib"
    log = tr.train(tiny, out)
    assert log["train_images"] == 20 and log["test_images_not_used"] == 5
    assert "no accuracy claim" in log["note"]
    assert json.loads(out.with_suffix(".train_log.json").read_text(encoding="utf-8"))["train_images"] == 20
    assert out.exists()


def test_trained_weights_load_through_the_env_variable(tiny, tmp_path, monkeypatch):
    out = tmp_path / "w.joblib"
    tr.train(tiny, out)
    monkeypatch.setenv("HCC_PIXEL_WEIGHTS", str(out))
    det = SyntheticPixelDetector()
    assert det.info.validated is False
    img = cv2.imread(str(tiny / "images" / "gen_proc_crack_0001.jpg"))
    assert isinstance(det.detect(img), list)


def test_training_without_a_dataset_says_how_to_make_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="generate"):
        tr.train(tmp_path / "nothing", tmp_path / "w.joblib")


# ---------------------------------------------------------------- C6 evaluation


def test_evaluation_scores_only_test_rows(tiny, tmp_path):
    out = tmp_path / "w.joblib"
    tr.train(tiny, out)
    rows = [r for r in tr.read_manifest(tiny) if r["split"] == "test"]
    assert len(rows) == 5
    per_type = ev.evaluate(SyntheticPixelDetector(out), tiny, rows)
    assert set(per_type) <= {d.value for d in LABEL_TO_DAMAGE.values()}


def test_shipped_report_keeps_generated_and_real_results_apart():
    assert "not accuracy on real" in EVAL["note"].lower()
    assert EVAL["real_images"]["result"] is None and EVAL["real_images"]["images"] == 0
    assert EVAL["test_images"] == 200
    assert "ليست دقة على جدران الطريف" in EVAL_MD
    assert "لا توجد" in EVAL_MD


def test_report_doc_matches_the_json_numbers():
    new = EVAL["models"]["trained_on_this_dataset"]
    old = EVAL["models"]["older_model_narrow_generator"]
    assert f"{new['macro_f1']:.3f}" in EVAL_MD and f"{new['macro_pixel_iou']:.3f}" in EVAL_MD
    assert f"{old['macro_f1']:.3f}" in EVAL_MD
    for t, v in new["per_type"].items():
        assert f"| {v['tp']} | {v['fp']} | {v['fn']} |" in EVAL_MD, t


def test_shipped_weights_and_log_exist_and_match_the_dataset_size():
    w = ROOT / "backend" / "app" / "vision" / "detectors" / "weights"
    log = json.loads((w / "generated_pixel_hgb.train_log.json").read_text(encoding="utf-8"))
    assert (w / "generated_pixel_hgb.joblib").exists()
    assert log["train_images"] == 800 and log["test_images_not_used"] == 200


def test_dataset_folder_is_gitignored():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "sample_data/generated_procedural/" in lines
