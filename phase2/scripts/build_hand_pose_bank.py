# phase2/scripts/build_hand_pose_bank.py

"""
Build the Real Hand Pose Bank
------------------------------
Generates phase2/data/hand_poses.json from Phase 1's captured MediaPipe
landmark data (phase1/data/raw/{train,val,test}.csv).

For every ISL class Phase 1 was trained on (digits 1-5, letters A-Z, and the
word gesture HELLO), this script averages the wrist-relative 21-point hand
landmarks across the ORIGINAL (non-augmented) captured samples for that
class, producing one clean, representative real hand pose per class.

This is what phase2/hand_animator.py animates between - real recorded
landmark data, not a synthetic or guessed hand shape.

Run whenever phase1's dataset changes or is re-collected:
    python phase2/scripts/build_hand_pose_bank.py
"""

import os
import csv
import json
from collections import defaultdict

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE2_DIR = os.path.dirname(_THIS_DIR)
PROJECT_ROOT = os.path.dirname(PHASE2_DIR)

RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "phase1", "data", "raw")
OUTPUT_PATH = os.path.join(PHASE2_DIR, "data", "hand_poses.json")

CSV_FILES = ["train.csv", "val.csv", "test.csv"]
NUM_LANDMARKS = 21


def _load_rows():
    rows = []
    for name in CSV_FILES:
        path = os.path.join(RAW_DATA_DIR, name)
        if not os.path.exists(path):
            print(f"  (skipping missing {name})")
            continue
        with open(path, "r", encoding="utf-8", newline="") as f:
            rows.extend(list(csv.DictReader(f)))
    return rows


def _landmarks_xy(row):
    """Extract the 21 (x, y) wrist-relative landmark points from a CSV row."""
    return [(float(row[f"lm{i}_x"]), float(row[f"lm{i}_y"])) for i in range(NUM_LANDMARKS)]


def _average(points_list):
    n = len(points_list)
    return [
        (
            round(sum(p[i][0] for p in points_list) / n, 4),
            round(sum(p[i][1] for p in points_list) / n, 4),
        )
        for i in range(NUM_LANDMARKS)
    ]


def build_pose_bank():
    rows = _load_rows()
    if not rows:
        raise FileNotFoundError(
            f"No landmark CSVs found under {RAW_DATA_DIR}. "
            "Run phase1/scripts/download_dataset.py first."
        )

    originals_by_label = defaultdict(list)
    all_by_label = defaultdict(list)

    for row in rows:
        label = row["label"]
        pts = _landmarks_xy(row)
        all_by_label[label].append(pts)
        if "aug_" not in row.get("image_path", ""):
            originals_by_label[label].append(pts)

    pose_bank = {}
    for label, all_pts in all_by_label.items():
        # Prefer averaging only the original (non-augmented) captures for a
        # cleaner pose; fall back to every sample if none exist.
        source = originals_by_label[label] or all_pts
        pose_bank[label] = _average(source)

    return pose_bank


def main():
    print("Building real hand pose bank from Phase 1 captured landmarks...")
    pose_bank = build_pose_bank()

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pose_bank, f, indent=1)

    print(f"Wrote {len(pose_bank)} class poses to {OUTPUT_PATH}")
    print("Classes:", ", ".join(sorted(pose_bank.keys())))


if __name__ == "__main__":
    main()