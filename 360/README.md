# 360° Image Processing Pipeline

This folder contains scripts for processing 360° equirectangular images through the SHARP model.

## Scripts

### `generate_vectors.py`

Main pipeline orchestrator. Takes a 360° equirectangular image, generates perspective views from multiple angles, and processes them through the SHARP model.

**Usage:**

```bash
python generate_vectors.py <n> <img>
```

**Arguments:**

| Argument | Type | Description |
|----------|------|-------------|
| `n` | int | Number of views. Must be 4, 6, 8, or 20 (platonic solid vertex counts). |
| `img` | Path | Path to the equirectangular input image. |

**Supported view counts:**

| n | Solid | FOV | Use case |
|---|-------|-----|----------|
| 4 | Tetrahedron | 110° | Sparse coverage, wide FOV |
| 6 | Octahedron | 90° | Cardinal directions only |
| 8 | Cube | 71° | Good balance for cubic projection |
| 20 | Dodecahedron | 42° | Dense coverage, narrow FOV |

**Example:**

```bash
python generate_vectors.py 8 path/to/panorama.jpg
```

This will:
1. Generate 8 view directions (yaw, pitch pairs) based on cube vertices
2. Convert the equirectangular image to 8 perspective views (71° FOV each)
3. Run SHARP batch processing on all generated views

**Output structure:**

```
path/
├── panorama.jpg              # Input image
└── panorama/                 # Generated views
    ├── 0.0_0.0_71.0.jpg     # Perspective view 1
    ├── 45.0_35.0_71.0.jpg   # Perspective view 2
    ...
    └── sharp_outputs/        # SHARP processed results (if configured)
```

---

### `convert360_wrapper.py`

Wrapper script that calls the external `convert360` tool to convert equirectangular images to perspective views. Also adds EXIF focal length metadata.

**Usage:**

```bash
python convert360_wrapper.py <input> [--resolution RES] [--fov FOV] [--yaw YAW] [--pitch PITCH] [-o OUTPUT]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `input` | (required) | Path to equirectangular input image |
| `--resolution` | 2048 | Output width/height in pixels |
| `--fov` | 90.0 | Field of view in degrees |
| `--yaw` | 0.0 | Yaw angle in degrees |
| `--pitch` | 0.0 | Pitch angle in degrees |
| `-o, --output` | auto | Output path (default: `{input_stem}/{yaw}_{pitch}_{fov}.jpg`) |

**Example:**

```bash
python convert360_wrapper.py panorama.jpg --yaw 45 --pitch -30 --fov 71
```

---

### `sharp_batch.py`

Batch processes images through the SHARP model using the `sharp predict` CLI command.

**Usage:**

```bash
python sharp_batch.py <input> [-o OUTPUT] [-c CHECKPOINT]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `input` | (required) | Directory containing input images |
| `-o, --output` | same as input | Output directory |
| `-c, --checkpoint` | None | Optional custom checkpoint file |

**Example:**

```bash
python sharp_batch.py ./panorama_views/ -o ./enhanced/
```

---

## Prerequisites

1. **convert360** - External tool for equirectangular to perspective conversion
2. **sharp** - SHARP model CLI (installed via `pip install -e .` from repo root)
3. **Python packages:**
   - `Pillow` (PIL)
   - `piexif`

## Installation

From the repository root:

```bash
pip install -e .
```

## Workflow

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│  Equirectangular │ --> │  Perspective Views  │ --> │  SHARP Enhanced │
│  Image (360°)    │     │  (n views, FOV)     │     │  Images         │
└─────────────────┘     └─────────────────────┘     └─────────────────┘
        │                         │                         │
        v                         v                         v
   generate_vectors.py      convert360_wrapper.py      sharp_batch.py
```

Typically you only need to run `generate_vectors.py` which orchestrates the entire pipeline.
