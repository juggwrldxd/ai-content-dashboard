#!/usr/bin/env python3
"""Strip Exif/metadata from images in a directory using Pillow.

Usage:
    python metadata_stripper.py /path/to/images

Handles: .jpg, .jpeg, .png, .webp
Saves files back in place.
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def strip_metadata(filepath: Path) -> bool:
    """Strip Exif/metadata from a single image file. Returns True on success."""
    try:
        img = Image.open(filepath)
        # Load pixel data so we can rebuild the image without metadata
        data = img.load()
        # Rebuild image — this drops ALL metadata (Exif, ICC, XMP, etc.)
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))

        # Preserve palette mode images (e.g. indexed PNGs)
        if img.mode == "P" and "palette" in img.info:
            clean.putpalette(img.getpalette())

        clean.save(filepath, format=img.format, quality=95)
        return True
    except Exception as exc:
        print(f"  [SKIP] {filepath.name}: {exc}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strip Exif/metadata from all images in a directory."
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Path to directory containing images",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be processed without modifying files",
    )
    args = parser.parse_args()

    target_dir = Path(args.directory).resolve()
    if not target_dir.is_dir():
        print(f"Error: '{target_dir}' is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    image_files = [
        p
        for p in sorted(target_dir.iterdir())
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not image_files:
        print("No supported image files found.")
        sys.exit(0)

    processed = 0
    skipped = 0

    for img_path in image_files:
        if args.dry_run:
            print(f"  [DRY-RUN] Would strip: {img_path.name}")
            processed += 1
            continue
        success = strip_metadata(img_path)
        if success:
            processed += 1
        else:
            skipped += 1

    print(f"\nDone. Processed: {processed}, Skipped: {skipped}")
    if processed > 0 and not args.dry_run:
        print("All metadata stripped from processed files.")


if __name__ == "__main__":
    main()