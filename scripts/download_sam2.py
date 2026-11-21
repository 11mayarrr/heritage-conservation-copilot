"""Download a SAM 2.1 checkpoint for the click-to-segment tool.

Usage: python scripts/download_sam2.py [tiny|small|base_plus|large]
Then set (printed at the end):
  HCC_SAM2_CHECKPOINT=models/sam2.1_hiera_<size>.pt
  HCC_SAM2_CONFIG=configs/sam2.1/sam2.1_hiera_<t|s|b+|l>.yaml

URLs are the ones used by the official facebookresearch/sam2 checkpoints/download_ckpts.sh.
Alternative without this script: HCC_SAM2_MODEL_ID=facebook/sam2.1-hiera-tiny (Hugging Face).
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/"
MODELS = {
    "tiny": ("sam2.1_hiera_tiny.pt", "configs/sam2.1/sam2.1_hiera_t.yaml"),
    "small": ("sam2.1_hiera_small.pt", "configs/sam2.1/sam2.1_hiera_s.yaml"),
    "base_plus": ("sam2.1_hiera_base_plus.pt", "configs/sam2.1/sam2.1_hiera_b+.yaml"),
    "large": ("sam2.1_hiera_large.pt", "configs/sam2.1/sam2.1_hiera_l.yaml"),
}


def main(size: str = "tiny") -> None:
    if size not in MODELS:
        sys.exit(f"choose one of {', '.join(MODELS)}")
    name, cfg = MODELS[size]
    out = Path(__file__).resolve().parents[1] / "models" / name
    out.parent.mkdir(exist_ok=True)
    if not out.exists():
        print(f"downloading {BASE + name} ...")
        urllib.request.urlretrieve(BASE + name, out)
    print(f"\nHCC_SEGMENTER=sam2\nHCC_SAM2_CHECKPOINT={out}\nHCC_SAM2_CONFIG={cfg}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tiny")
