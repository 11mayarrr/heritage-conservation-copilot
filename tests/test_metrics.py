from app.evaluation.metrics import match_instances, pixel_iou, summarize

SQ = [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]]
FAR = [[0.6, 0.6], [0.8, 0.6], [0.8, 0.8], [0.6, 0.8]]


def test_metrics_tp_fp_fn():
    preds = [{"damage_type": "crack", "polygon": SQ, "confidence": 0.6},
             {"damage_type": "crack", "polygon": FAR, "confidence": 0.5}]
    truth = [{"damage_type": "crack", "polygon": SQ},
             {"damage_type": "plaster_loss", "polygon": FAR}]
    counts = match_instances(preds, truth)
    assert counts["crack"] == {"tp": 1, "fp": 1, "fn": 0}
    assert counts["plaster_loss"] == {"tp": 0, "fp": 0, "fn": 1}
    rep = summarize(counts, pixel_iou(preds, truth))
    assert rep["crack"]["precision"] == 0.5 and rep["crack"]["recall"] == 1.0
    assert abs(rep["crack"]["f1"] - 2 / 3) < 1e-9
    assert rep["plaster_loss"]["precision"] is None  # undefined, not invented
    assert rep["plaster_loss"]["pixel_iou"] == 0.0


def test_agent_snapshot_is_kept_for_evaluation(client, samples):
    w = client.post("/api/walls", json={"code": "W-9"}).json()
    with open(samples / "synthetic_wall_T1.jpg", "rb") as f:
        insp = client.post("/api/inspections", data={"wall_id": w["id"]}, files={"image": ("a.jpg", f, "image/jpeg")}).json()
    assert len(insp["analysis"]["agent_detections"]) == len(insp["regions"])
