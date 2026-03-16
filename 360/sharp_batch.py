#!/usr/bin/env python3
"""Batch process images with SHARP model."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_sharp(input_dir: Path, output_dir: Path, checkpoint: Path | None = None) -> None:
    """Run sharp predict on input directory."""
    cmd = [
        "sharp",
        "predict",
        "-i", str(input_dir),
        "-o", str(output_dir),
    ]
    
    if checkpoint:
        cmd.extend(["-c", str(checkpoint)])
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    
    if result.returncode != 0:
        print(f"Error running sharp: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    
    if result.stdout:
        print(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch process images with SHARP model."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to folder containing input images",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: same as input)",
    )
    parser.add_argument(
        "-c",
        "--checkpoint",
        type=Path,
        default=None,
        help="Path to custom checkpoint file (optional)",
    )
    
    args = parser.parse_args()
    
    if not args.input.exists() or not args.input.is_dir():
        print(f"Error: Input directory not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    output_dir = args.output if args.output else args.input
    output_dir.mkdir(parents=True, exist_ok=True)
    
    run_sharp(args.input, output_dir, args.checkpoint)
    
    print(f"Successfully processed images from {args.input}")
    print(f"Output saved to {output_dir}")


if __name__ == "__main__":
    main()