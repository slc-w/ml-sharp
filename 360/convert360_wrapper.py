#!/usr/bin/env python3
"""Wrapper script to call convert360 and add EXIF focal length metadata."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

from PIL import  Image
import piexif


def calculate_focal_length(fov_degrees: float) -> float:
    """Calculate focal length in 35mm equivalent from FOV.

    Formula: focal_length = 18 / tan(fov / 2)
    """
    fov_rad = math.radians(fov_degrees)
    focal_length = 18 / math.tan(fov_rad / 2)
    return focal_length


def add_exif_focal_length(image_path: Path, focal_length: float) -> None:
    """ add EXIF tags FocalLengthIn35mmFilm and FocalLength to image."""
    # Load existing EXIF data
    exif_dict = piexif.load(str(image_path))

    # Set FocalLengthIn35mmFilm (tag 0xA405) to the calculated focal length
    exif_dict["Exif"][piexif.ExifIFD.FocalLengthIn35mmFilm] = int(focal_length)

    # Set FocalLength (tag 0x920A) to the calculated focal length as a rational number
    focal_length_rational = (int(focal_length * 100), 100)  # e.g. 50.0 -> (5000, 100)
    exif_dict["Exif"][piexif.ExifIFD.FocalLength] = focal_length_rational

    # Save updated EXIF data back to the image
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, str(image_path))


def run_convert360(
    input_path: Path,
    output_path: Path,
    h_fov: float,
    v_fov: float,
    width: int,
    height: int,
    yaw: float,
    pitch: float,
) -> None:
    """Execute convert360 command."""
    cmd = [
        "convert360",
        "e2p",
        str(input_path),
        str(output_path),
        "--h-fov",
        str(h_fov),
        "--v-fov",
        str(v_fov),
        "--width",
        str(width),
        "--height",
        str(height),
        "--yaw",
        str(yaw),
        "--pitch",
        str(pitch),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running convert360: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    if result.stdout:
        print(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert equirectangular image to perspective and add EXIF focal length."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the equirectangular input image",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=2048,
        help="Output image resolution (width and height, default: 2048)",
    )
    parser.add_argument(
        "--fov",
        type=float,
        default=90.0,
        help="Field of view in degrees (default: 90)",
    )
    parser.add_argument(
        "--yaw",
        type=float,
        default=0.0,
        help="Yaw angle in degrees (default: 0)",
    )
    parser.add_argument(
        "--pitch",
        type=float,
        default=0.0,
        help="Pitch angle in degrees (default: 0)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: input_name_<yaw>_<pitch>_<fov>.jpg)",
    )

    args = parser.parse_args()

    # Validate input exists
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output is None:
        input_stem = args.input.stem
        # Create folder with input name (without extension)
        output_dir = args.input.parent / input_stem
        output_dir.mkdir(parents=True, exist_ok=True)
        # Name file as <yaw>_<pitch>_<fov>.jpg
        output_filename = f"{args.yaw}_{args.pitch}_{args.fov}.jpg"
        output_path = output_dir / output_filename
    else:
        output_path = args.output
        # Ensure .jpg extension
        if output_path.suffix.lower() not in (".jpg", ".jpeg"):
            output_path = output_path.with_suffix(".jpg")

    # Run convert360
    run_convert360(
        input_path=args.input,
        output_path=output_path,
        h_fov=args.fov,
        v_fov=args.fov,
        width=args.resolution,
        height=args.resolution,
        yaw=args.yaw,
        pitch=args.pitch,
    )

    # Calculate and add EXIF focal length
    focal_length = calculate_focal_length(args.fov)
    print(f"Calculated focal length: {focal_length:.2f}mm (35mm equivalent)")

    add_exif_focal_length(output_path, focal_length)

    print(f"Successfully created: {output_path}")


if __name__ == "__main__":
    main()
