import numpy as np

from app.vision.detectors import get_detector
from app.vision.synthetic import LABEL_TO_DAMAGE, make_labeled


def test_generator_is_deterministic_and_covers_all_labels():
    a, la = make_labeled(5)
    b, lb = make_labeled(5)
    assert np.array_equal(a, b) and np.array_equal(la, lb)
    seen = set()
    for seed in range(30):
        seen |= set(np.unique(make_labeled(seed)[1]).tolist())
    assert set(LABEL_TO_DAMAGE) <= seen


def test_synthetic_model_is_labeled_unvalidated_and_finds_held_out_damage():
    det = get_detector("synthetic_model")
    assert det.info.kind == "model" and det.info.validated is False
    found: set[str] = set()
    for seed in range(100_000, 100_008):  # disjoint from training seeds 0..149
        img, lab = make_labeled(seed)
        for d in det.detect(img):
            assert d.confidence_source.value == "model_synthetic_only"
            assert d.confidence < 0.7
            found.add(d.damage_type.value)
    assert {"crack", "moisture_erosion", "plaster_loss"} <= found
