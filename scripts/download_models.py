"""Download the YuNet face detector used for face anonymization.

The model is already committed in backend/app/privacy/models/. Run this only to
restore it if it was deleted. Without it the system falls back to Haar cascades,
which miss tilted, small, dim or partly covered faces (see tests/test_face_privacy.py).

    python scripts/download_models.py
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "backend" / "app" / "privacy" / "models"
MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
}


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for name, (url, sha) in MODELS.items():
        path = DEST / name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == sha:
            print(f"ok      {name}")
            continue
        print(f"get     {name}")
        data = urllib.request.urlopen(url, timeout=60).read()
        got = hashlib.sha256(data).hexdigest()
        if got != sha:
            print(f"checksum mismatch for {name}: {got}", file=sys.stderr)
            return 1
        path.write_bytes(data)
        print(f"saved   {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
