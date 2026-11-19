"""The inspection agent as a LangGraph state machine.

Mirrors the challenge's action map (slide 15):

  quality_check ──(invalid)──> request_retake ─> END
        │valid
  anonymize_faces ─> detect_damage ─> score_confidence ─> assess_sufficiency
        ─> retrieve_treatments ─> build_atlas ─> END (awaiting expert review)

Expert review, correction, re-analysis and approval (steps 8-10) are
human-in-the-loop actions exposed through the API, not automated nodes: the
agent proposes, the conservator decides.
"""
from __future__ import annotations

from typing import Any, TypedDict

import numpy as np
from langgraph.graph import END, StateGraph

from app.agents.rules import assess_sufficiency, needs_field_inspection, priority_for
from app.config import get_settings
from app.privacy.anonymizer import anonymize
from app.rag.knowledge_base import get_kb
from app.vision.detectors import get_detector
from app.vision.geometry import grid_cells, polygon_area
from app.vision.quality import assess_quality


class InspectionState(TypedDict, total=False):
    image: np.ndarray  # original, in memory only
    anonymized: np.ndarray
    quality: dict
    privacy: dict
    detector: dict
    detections: list[dict]
    sufficiency: dict
    recommendations: dict  # damage_type -> retrieval result
    grid: dict
    status: str
    trace: list[str]


def _log(state: InspectionState, msg: str) -> list[str]:
    return [*state.get("trace", []), msg]


def quality_check(state: InspectionState) -> dict[str, Any]:
    q = assess_quality(state["image"]).to_dict()
    return {"quality": q, "trace": _log(state, f"quality_check: acceptable={q['acceptable']}")}


def route_quality(state: InspectionState) -> str:
    return "anonymize_faces" if state["quality"]["acceptable"] else "request_retake"


def request_retake(state: InspectionState) -> dict[str, Any]:
    return {"status": "rejected_quality", "detections": [], "trace": _log(state, "request_retake")}


def anonymize_faces(state: InspectionState) -> dict[str, Any]:
    s = get_settings()
    anon, info = anonymize(state["image"], method=s.face_method)
    # Drop the original from state: every later step sees only the anonymized image.
    return {
        "anonymized": anon,
        "image": anon,
        "privacy": info,
        "trace": _log(state, f"anonymize_faces: hidden={info['faces_hidden']}"),
    }


def detect_damage(state: InspectionState) -> dict[str, Any]:
    det = get_detector()
    found = det.detect(state["anonymized"])
    detections = [
        {
            "damage_type": d.damage_type.value,
            "polygon": d.polygon,
            "confidence": d.confidence,
            "confidence_source": d.confidence_source.value,
            "description": d.description,
            "evidence": d.evidence,
        }
        for d in found
    ]
    info = det.info.__dict__
    return {"detector": info, "detections": detections, "trace": _log(state, f"detect_damage: {len(detections)} via {info['name']}")}


def score_confidence(state: InspectionState) -> dict[str, Any]:
    s = get_settings()
    out = []
    for d in state["detections"]:
        area = polygon_area(d["polygon"])
        out.append(
            {
                **d,
                "area_fraction": round(area, 5),
                "grid_cells": grid_cells(d["polygon"], s.grid_cols, s.grid_rows),
                "priority": priority_for(d["damage_type"], area, d.get("evidence")).value,
                "low_confidence": d["confidence"] < s.low_confidence_threshold,
                "needs_field_inspection": needs_field_inspection(
                    d["damage_type"], d["confidence"], s.low_confidence_threshold
                ),
            }
        )
    out.sort(key=lambda d: (d["grid_cells"][0][1:].zfill(3), d["grid_cells"][0][0]))
    return {
        "detections": out,
        "grid": {"cols": s.grid_cols, "rows": s.grid_rows, "type": "temporary"},
        "trace": _log(state, "score_confidence"),
    }


def assess_image_sufficiency(state: InspectionState) -> dict[str, Any]:
    s = get_settings()
    suff = assess_sufficiency(
        state["quality"], state["detections"], s.low_confidence_threshold, state["detector"]["kind"]
    )
    return {"sufficiency": suff, "trace": _log(state, f"assess_sufficiency: {suff['sufficient']}")}


def retrieve_treatments(state: InspectionState) -> dict[str, Any]:
    kb = get_kb()
    recs = {}
    for dt in sorted({d["damage_type"] for d in state["detections"]}):
        ctx = " ".join(d["description"] for d in state["detections"] if d["damage_type"] == dt)
        recs[dt] = kb.retrieve(dt, ctx)
    return {"recommendations": recs, "trace": _log(state, f"retrieve_treatments: {list(recs)}")}


def build_atlas(state: InspectionState) -> dict[str, Any]:
    return {"status": "in_review", "trace": _log(state, "build_atlas: awaiting expert review")}


def build_graph():
    g = StateGraph(InspectionState)
    g.add_node("quality_check", quality_check)
    g.add_node("request_retake", request_retake)
    g.add_node("anonymize_faces", anonymize_faces)
    g.add_node("detect_damage", detect_damage)
    g.add_node("score_confidence", score_confidence)
    g.add_node("assess_sufficiency", assess_image_sufficiency)
    g.add_node("retrieve_treatments", retrieve_treatments)
    g.add_node("build_atlas", build_atlas)

    g.set_entry_point("quality_check")
    g.add_conditional_edges("quality_check", route_quality, {
        "anonymize_faces": "anonymize_faces",
        "request_retake": "request_retake",
    })
    g.add_edge("request_retake", END)
    g.add_edge("anonymize_faces", "detect_damage")
    g.add_edge("detect_damage", "score_confidence")
    g.add_edge("score_confidence", "assess_sufficiency")
    g.add_edge("assess_sufficiency", "retrieve_treatments")
    g.add_edge("retrieve_treatments", "build_atlas")
    g.add_edge("build_atlas", END)
    return g.compile()


_graph = None


def run_inspection(image: np.ndarray) -> InspectionState:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph.invoke({"image": image, "trace": []})
