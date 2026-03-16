#!/usr/bin/env python3
"""Generate view vectors and process 360° equirectangular images through SHARP pipeline."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path


phi = (1 + math.sqrt(5)) / 2


def to_spherical(pts):
    """Converts (x, y, z) to (yaw, pitch) in degrees."""
    return [
        (
            round(math.atan2(y, x) * 180 / math.pi, 4),  # yaw
            round(math.acos(z / math.sqrt(x * x + y * y + z * z)) * 180 / math.pi - 90, 4),  # pitch
        )
        for x, y, z in pts
    ]


SOLIDS = {
    4: {"fov": 110, "vertices": [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]},
    6: {"fov": 90, "vertices": [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]},
    8: {"fov": 71, "vertices": [(x, y, z) for x in [-1, 1] for y in [-1, 1] for z in [-1, 1]]},
    20: {"fov": 42, "vertices": [
        (0, 1, phi), (0, 1, -phi), (0, -1, phi), (0, -1, -phi),
        (1, phi, 0), (1, -phi, 0), (-1, phi, 0), (-1, -phi, 0),
        (phi, 0, 1), (phi, 0, -1), (-phi, 0, 1), (-phi, 0, -1)
    ]}
}


VALID_N = {4, 6, 8, 20}


def get_vectors(n: int) -> list[tuple[float, float]]:
    """Get (yaw, pitch) vectors for n views."""
    return to_spherical(SOLIDS[n]["vertices"])


def run_convert360_wrapper(
    input_path: Path,
    yaw: float,
    pitch: float,
    fov: float,
    resolution: int = 2048,
) -> Path:
    """Run convert360_wrapper.py for a single view. Returns output directory."""
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "convert360_wrapper.py"),
        str(input_path),
        "--yaw", str(yaw),
        "--pitch", str(pitch),
        "--fov", str(fov),
        "--resolution", str(resolution),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running convert360_wrapper: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    if result.stdout:
        print(result.stdout)

    # Return the output directory (convert360_wrapper creates input_stem/ subfolder)
    return input_path.parent / input_path.stem


def run_sharp_batch(input_dir: Path) -> None:
    """Run sharp_batch.py on input directory."""
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "sharp_batch.py"),
        str(input_dir),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running sharp_batch: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    if result.stdout:
        print(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate view vectors from 360° image and process through SHARP."
    )
    parser.add_argument(
        "n",
        type=int,
        help="Number of views (must be 4, 6, 8, or 20)",
    )
    parser.add_argument(
        "img",
        type=Path,
        help="Path to equirectangular input image",
    )

    args = parser.parse_args()

    # Validate n
    if args.n not in VALID_N:
        print(
            f"Error: n must be one of {sorted(VALID_N)} (platonic solid vertex counts). "
            f"Got: {args.n}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate input image exists
    if not args.img.exists():
        print(f"Error: Input image not found: {args.img}", file=sys.stderr)
        sys.exit(1)

    # Get view vectors
    vectors = get_vectors(args.n)
    fov = SOLIDS[args.n]["fov"]

    print(f"\nProcessing {args.img.name} with {args.n} views (FOV: {fov}°)")
    print(f"View directions (yaw, pitch):")
    for i, (yaw, pitch) in enumerate(vectors, 1):
        print(f"  {i}: ({yaw}°, {pitch}°)")
    print()

    # Generate perspective views
    output_dir = None
    for i, (yaw, pitch) in enumerate(vectors, 1):
        print(f"[{i}/{args.n}] Converting view at ({yaw}°, {pitch}°)...")
        output_dir = run_convert360_wrapper(args.img, yaw, pitch, fov)

    assert output_dir is not None, "output_dir should not be None after processing views"
    print(f"\nPerspective views saved to: {output_dir}")

    # Run SHARP batch processing
    print(f"\nRunning SHARP batch processing...")
    run_sharp_batch(output_dir)

    print(f"\nPipeline complete!")
    print(f"  Input: {args.img}")
    print(f"  Perspective views: {output_dir}")
    print(f"  SHARP outputs: {output_dir}")


if __name__ == "__main__":
    main()

