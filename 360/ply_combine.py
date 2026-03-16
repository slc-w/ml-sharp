import argparse
import sys
from pathlib import Path
import os
import numpy as np
from plyfile import PlyData, PlyElement

def load_ply(path):
    """Load Gaussian splat data from a PLY file."""
    plydata = PlyData.read(path)
    # Extract properties (positions, opacity, rotation, scaling, shs)
    # Note: Structure may vary slightly based on the implementation
    return plydata['vertex']

def combine_gaussians(ply_paths, output_path):
    """Combines multiple PLY gaussian files into one."""
    combined_data = {}
    
    # Load all splats
    all_splats = [load_ply(p) for p in ply_paths]
    
    # Combine each property
    # This requires identical structure across PLY files
    combined_elements = []
    
    # Combine vertex arrays
    # A more robust script would handle different property formats
    combined_vertex = np.concatenate([s.data for s in all_splats])
    
    # Create new PLY element
    new_element = PlyElement.describe(
        'vertex', 
        [
            (prop.name, prop.dtype) 
            for prop in all_splats[0].properties
        ],
        combined_vertex
    )
    
    # Save combined PLY
    PlyData([new_element]).write(output_path)
    print(f"Saved {len(combined_vertex)} points to {output_path}")


def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Combine multiple Gaussian splat PLY files into one.'
    )
    parser.add_argument(
        'input',
        type=Path,
        nargs='+',
        help='Input PLY file paths (one or more)'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('combined.ply'),
        help='Output PLY file path (default: combined.ply)'
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = get_args()

    # Validate input files exist
    for ply_path in args.input:
        if not ply_path.exists():
            print(f"Error: Input file not found: {ply_path}", file=sys.stderr)
            sys.exit(1)
        if not ply_path.suffix.lower() == '.ply':
            print(f"Warning: File may not be a PLY file: {ply_path}", file=sys.stderr)

    # Convert Path objects to strings for combine_gaussians
    input_paths = [str(p) for p in args.input]
    output_path = "combined.ply"
    if args.output is not None:
        output_path = args.output



    combine_gaussians(input_paths, output_path)


if __name__ == "__main__":
    main()
