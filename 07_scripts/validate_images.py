#!/usr/bin/env python3
"""
validate_images.py — Batch image validation pipeline.

Validates generated images using OpenCV:
  - Face detection (Haar cascade)
  - Minimum resolution 1024×1024
  - Blur detection (Laplacian variance)
  - Pixel-similarity face consistency check (placeholder)

Usage:
    python validate_images.py /path/to/batch_directory

Passing images → 01_processing/image_validation/validated/
Failing images  → 01_processing/image_validation/rejected/
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

# ── constants ────────────────────────────────────────────────────────────────
MIN_WIDTH = 1024
MIN_HEIGHT = 1024
LAPLACIAN_THRESHOLD = 100.0          # below this → blurry
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

BASE_DIR = Path(__file__).resolve().parent.parent  # ~/ai_content_business/
VALIDATED_DIR = BASE_DIR / "01_processing" / "image_validation" / "validated"
REJECTED_DIR = BASE_DIR / "01_processing" / "image_validation" / "rejected"


# ── haar cascade loader (lazy) ───────────────────────────────────────────────
def _get_face_cascade():
    """Load the OpenCV Haar cascade for frontal faces."""
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    if cascade.empty():
        raise RuntimeError(f"Failed to load Haar cascade from {cascade_path}")
    return cascade


# ── individual checks ────────────────────────────────────────────────────────
def check_resolution(img: np.ndarray) -> tuple[bool, str]:
    """Return (pass, reason) for minimum 1024×1024."""
    h, w = img.shape[:2]
    if w >= MIN_WIDTH and h >= MIN_HEIGHT:
        return True, f"{w}x{h}"
    return False, f"{w}x{h} (below {MIN_WIDTH}x{MIN_HEIGHT})"


def check_blur(img: np.ndarray) -> tuple[bool, str]:
    """Return (pass, reason) for Laplacian variance blur check."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var >= LAPLACIAN_THRESHOLD:
        return True, f"Laplacian var={laplacian_var:.1f}"
    return False, f"Laplacian var={laplacian_var:.1f} (blurry, threshold={LAPLACIAN_THRESHOLD})"


def check_face(img: np.ndarray, cascade) -> tuple[bool, str]:
    """Return (pass, reason) for face detection."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(64, 64))
    if len(faces) > 0:
        sizes = ", ".join(f"{w}x{h}" for (x, y, w, h) in faces)
        return True, f"{len(faces)} face(s) detected [{sizes}]"
    return False, "No face detected"


# ── placeholder face-consistency comparison ──────────────────────────────────
def face_consistency_report(passing_paths: list[Path]) -> list[str]:
    """
    Basic pixel-similarity comparison between all pairs of passing images.
    This is a placeholder — real face-consistency would use embeddings.
    Returns a list of human-readable comparison lines.
    """
    if len(passing_paths) < 2:
        return ["Fewer than 2 images passed — skipping face consistency check."]

    lines = [f"Face consistency comparison ({len(passing_paths)} images):"]
    imgs = []
    for p in passing_paths:
        img = cv2.imread(str(p))
        if img is not None:
            imgs.append(img)

    for i in range(len(imgs)):
        for j in range(i + 1, len(imgs)):
            # Resize both to the same size for pixel comparison
            h = min(imgs[i].shape[0], imgs[j].shape[0])
            w = min(imgs[i].shape[1], imgs[j].shape[1])
            a = cv2.resize(imgs[i], (w, h))
            b = cv2.resize(imgs[j], (w, h))

            diff = cv2.absdiff(a, b)
            mse = np.mean(diff ** 2)
            similarity = max(0.0, 100.0 - (mse / 100.0))  # crude: lower MSE → higher similarity

            lines.append(
                f"  [{passing_paths[i].name}] vs [{passing_paths[j].name}]: "
                f"MSE={mse:.2f}, similarity≈{similarity:.1f}%"
            )
    return lines


# ── main ─────────────────────────────────────────────────────────────────────
def validate_batch(batch_dir: str) -> None:
    batch_path = Path(batch_dir).resolve()
    if not batch_path.is_dir():
        print(f"Error: '{batch_dir}' is not a directory.")
        sys.exit(1)

    # Ensure output directories exist
    VALIDATED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)

    # Gather image files
    image_files = sorted(
        p for p in batch_path.iterdir()
        if p.suffix.lower() in VALID_EXTENSIONS and p.is_file()
    )
    if not image_files:
        print(f"No image files found in '{batch_dir}'.")
        sys.exit(0)

    cascade = _get_face_cascade()

    passed: list[Path] = []
    rejected: list[tuple[Path, str]] = []

    for img_path in image_files:
        try:
            img = cv2.imread(str(img_path))
            if img is None:
                rejected.append((img_path, "Unreadable / corrupted image"))
                continue

            reasons: list[str] = []

            res_ok, res_msg = check_resolution(img)
            if not res_ok:
                reasons.append(res_msg)

            blur_ok, blur_msg = check_blur(img)
            if not blur_ok:
                reasons.append(blur_msg)

            face_ok, face_msg = check_face(img, cascade)
            if not face_ok:
                reasons.append(face_msg)

            if not reasons:
                passed.append(img_path)
            else:
                rejected.append((img_path, "; ".join(reasons)))

        except Exception as exc:
            rejected.append((img_path, f"Exception: {exc}"))

    # ── move files ────────────────────────────────────────────────────────
    for p in passed:
        dest = VALIDATED_DIR / p.name
        shutil.move(str(p), str(dest))

    for p, reason in rejected:
        dest = REJECTED_DIR / p.name
        shutil.move(str(p), str(dest))

    # ── summary ───────────────────────────────────────────────────────────
    print(f"{len(passed)} good, {len(rejected)} rejected")
    print()

    if rejected:
        print("Rejected files:")
        for p, reason in rejected:
            print(f"  {p.name}  →  {reason}")
        print()

    # ── face consistency (placeholder) ────────────────────────────────────
    consistency_lines = face_consistency_report(passed)
    for line in consistency_lines:
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate generated images using OpenCV."
    )
    parser.add_argument(
        "batch_dir",
        help="Path to a directory containing generated images to validate.",
    )
    args = parser.parse_args()
    validate_batch(args.batch_dir)


if __name__ == "__main__":
    main()