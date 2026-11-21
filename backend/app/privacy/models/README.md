# Face detection models

| File | Source | License |
|---|---|---|
| `face_detection_yunet_2023mar.onnx` | [OpenCV Zoo, YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) (Wu et al., 2023) | MIT |
| `haarcascade_frontalface_default.xml`, `haarcascade_profileface.xml` | OpenCV `data/haarcascades` | Intel License Agreement (BSD-style), bundled with OpenCV |

YuNet is used when present; the Haar cascades are the fallback.
SHA-256 of the YuNet file: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
Restore it with `python scripts/download_models.py`.

Measured on the test fixtures (`tests/test_face_privacy.py`, `tests/fixtures/`):

| Case | Haar | YuNet |
|---|---|---|
| Upright face, large or small | hidden | hidden |
| Face tilted 25° / 30° / 45° | **missed** | hidden |
| Very small face (~70 px wide) | **missed** | hidden (plus one small false box beside it) |
| Dim / backlit face | **missed** | hidden |
| Face half covered | **missed** | hidden |
| Wall with no people | no boxes | no boxes |

These are composited test photos, not field photos from At-Turaif. Manual blur
in the UI remains necessary for anything the detector misses.
