
import os
import numpy as np
import argparse
from io import BytesIO
from dataclasses import dataclass

from plyfile import PlyData, PlyElement
from scipy.spatial.transform import Rotation

from sh_utils import SHRotator


def get_args():
  parser = argparse.ArgumentParser(
    description='Rotate and transform PLY/splat files.'
  )
  parser.add_argument('-i', '--input', type=str, required=True,
            help='Input PLY file path')
  parser.add_argument('-o', '--output', type=str, default=None,
            help='Output file path (.ply or .splat). If not provided, input file will be replaced.')
  parser.add_argument('--position', type=float, nargs=3, 
            default=[0.0, 0.0, 0.0],
            metavar=('X', 'Y', 'Z'),
            help='Translation position (default: 0 0 0)')
  parser.add_argument('--rotation', type=float, nargs=3, 
            default=[0.0, 0.0, 0.0],
            metavar=('RX', 'RY', 'RZ'),
            help='Rotation in degrees around x, y, z axes (default: 0 0 0)')
  parser.add_argument('--scale', type=float, nargs=3, 
            default=[1.0, 1.0, 1.0],
            metavar=('SX', 'SY', 'SZ'),
            help='Scale factors (default: 1 1 1)')
  parser.add_argument('--unity-transform', action='store_true',
            help='Apply Unity coordinate system transformation')
  parser.add_argument('--rotate-sh', action='store_true',
            help='Rotate spherical harmonics')
  parser.add_argument('--max-sh-degree', type=int, default=3,
            help='Maximum spherical harmonics degree (default: 3)')
  parser.add_argument('--enable-transform', action='store_true', default=True,
            help='Enable transformation (default: True)')
  parser.add_argument('--no-transform', dest='enable_transform', action='store_false',
            help='Disable transformation')

  return parser.parse_args()

@dataclass
class SplatData:
  xyz: np.ndarray
  features_dc: np.ndarray
  features_rest: np.ndarray
  opacity: np.ndarray
  scaling: np.ndarray
  rotation: np.ndarray
  active_sh_degree: int

def get_shs(data: SplatData):
  return np.concatenate([data.features_dc, data.features_rest], axis=-1)

def transform_xyz(T, R, S, xyz):
  return xyz @ (R @ S).T + T

def batch_compose_rs(R2, S2, r1, s1):
  w, x, y, z = r1.T # (4, n)
  R1 = Rotation.from_quat(np.stack([x, y, z, w], axis=-1)).as_matrix()
  S1 = np.eye(3) * s1[..., np.newaxis]
  
  R2S2 = R2 @ S2
  R1S1 = np.einsum('bij,bjk->bik', R1, S1)
  RS = np.einsum('ij,bjk->bik', R2S2, R1S1)
  return RS

def batch_decompose_rs(RS):
  sx = np.linalg.norm(RS[..., 0], axis=-1)
  sy = np.linalg.norm(RS[..., 1], axis=-1)
  sz = np.linalg.norm(RS[..., 2], axis=-1)
  
  RS[..., 0] /= sx[..., np.newaxis]
  RS[..., 1] /= sy[..., np.newaxis]
  RS[..., 2] /= sz[..., np.newaxis]
  x, y, z, w = Rotation.from_matrix(RS).as_quat().T
  r = np.stack([w, x, y, z], axis=-1)
  s = np.stack([sx, sy, sz], axis=-1)
  return r, s

def batch_rotate_sh(R, shs_in, max_sh_degree=3):
  # shs_in: (n, 3, deg)
  # SH is in yzx order so here shift the order of rot mat
  rot_fn = SHRotator(R, deg=max_sh_degree)
  shs_out = np.stack([
    rot_fn(shs_in[..., 0, :]),
    rot_fn(shs_in[..., 1, :]),
    rot_fn(shs_in[..., 2, :])
  ], axis=-2)
  return shs_out

def transform_data(args, data: SplatData):
  position = np.asarray(args.position, dtype=np.float32)
  rotation = np.asarray(args.rotation, dtype=np.float32)
  scale = np.asarray(args.scale, dtype=np.float32)

  if args.unity_transform:
    x, y, z = rotation
    q = Rotation.from_euler('zxy', [z, x, y], degrees=True).as_quat()
    q = Rotation.from_quat([-q[0], -q[2], -q[1], q[3]])
    q_shift_r = np.pi/4
    q_shift_r = Rotation.from_quat([np.sin(q_shift_r), 0., 0., np.cos(q_shift_r)])
    q_shift_l = Rotation.from_euler('xyz', [90, 180, 0], degrees=True)
    q = q_shift_l * q * q_shift_r
    rotation = q.as_euler('xyz', degrees=True)
    position[0] = -position[0]
    position[1] = -position[1]
    position[2] = -position[2]

  # object to world
  S = np.eye(3) * scale
  R = Rotation.from_euler('xyz', rotation, degrees=True).as_matrix()
  T = np.array(position, dtype=np.float32)
  data.xyz = transform_xyz(T, R, S, data.xyz)
  r, s = data.rotation, np.exp(data.scaling)
  RS = batch_compose_rs(R, S, r, s)
  r, s = batch_decompose_rs(RS)
  data.rotation, data.scaling = r, np.log(s)
  if args.rotate_sh:
    shs_out = batch_rotate_sh(R, get_shs(data), args.max_sh_degree)
    data.features_dc = shs_out[..., :, :1]
    data.features_rest = shs_out[..., :, 1:]
  return data

def construct_list_of_attributes(data: SplatData):
  l = ['x', 'y', 'z', 'nx', 'ny', 'nz']
  # All channels except the 3 DC
  for i in range(data.features_dc.shape[1]*data.features_dc.shape[2]):
    l.append('f_dc_{}'.format(i))
  for i in range(data.features_rest.shape[1]*data.features_rest.shape[2]):
    l.append('f_rest_{}'.format(i))
  l.append('opacity')
  for i in range(data.scaling.shape[1]):
    l.append('scale_{}'.format(i))
  for i in range(data.rotation.shape[1]):
    l.append('rot_{}'.format(i))
  return l

def mkdirs(path):
  if path:
    os.makedirs(path, exist_ok=True)

def load_ply(path, max_sh_degree=3):
  plydata = PlyData.read(path)

  xyz = np.stack([
    np.asarray(plydata.elements[0]["x"]),
    np.asarray(plydata.elements[0]["y"]),
    np.asarray(plydata.elements[0]["z"])
  ], axis=1)
  opacities = np.asarray(plydata.elements[0]["opacity"])[..., np.newaxis]

  features_dc = np.zeros((xyz.shape[0], 3, 1))
  features_dc[:, 0, 0] = np.asarray(plydata.elements[0]["f_dc_0"])
  features_dc[:, 1, 0] = np.asarray(plydata.elements[0]["f_dc_1"])
  features_dc[:, 2, 0] = np.asarray(plydata.elements[0]["f_dc_2"])

  extra_f_names = [p.name for p in plydata.elements[0].properties if p.name.startswith("f_rest_")]
  extra_f_names = sorted(extra_f_names, key = lambda x: int(x.split('_')[-1]))
  
  # Auto-detect SH degree from file
  num_extra_coeffs = len(extra_f_names)
  if num_extra_coeffs == 0:
    detected_sh_degree = 0
  else:
    # Solve: num_extra_coeffs = 3 * (deg + 1)^2 - 3 for deg
    import math
    detected_sh_degree = int(math.isqrt((num_extra_coeffs + 3) // 3)) - 1
    # Clamp to max_sh_degree
    detected_sh_degree = min(detected_sh_degree, max_sh_degree)
  
  print(f':: Detected SH degree: {detected_sh_degree} (found {num_extra_coeffs} extra coefficients)')
  
  # Only use coefficients up to the detected degree
  expected_extra = 3 * (detected_sh_degree + 1)**2 - 3 if detected_sh_degree > 0 else 0
  extra_f_names = extra_f_names[:expected_extra] if expected_extra > 0 else []
  
  features_extra = np.zeros((xyz.shape[0], len(extra_f_names)))
  for idx, attr_name in enumerate(extra_f_names):
    features_extra[:, idx] = np.asarray(plydata.elements[0][attr_name])
  # Reshape (P,F*SH_coeffs) to (P, F, SH_coeffs except DC)
  if len(extra_f_names) > 0:
    features_extra = features_extra.reshape((features_extra.shape[0], 3, (detected_sh_degree + 1) ** 2 - 1))
  else:
    features_extra = features_extra.reshape((features_extra.shape[0], 3, 0))

  scale_names = [p.name for p in plydata.elements[0].properties if p.name.startswith("scale_")]
  scale_names = sorted(scale_names, key = lambda x: int(x.split('_')[-1]))
  scales = np.zeros((xyz.shape[0], len(scale_names)))
  for idx, attr_name in enumerate(scale_names):
    scales[:, idx] = np.asarray(plydata.elements[0][attr_name])

  rot_names = [p.name for p in plydata.elements[0].properties if p.name.startswith("rot")]
  rot_names = sorted(rot_names, key = lambda x: int(x.split('_')[-1]))
  rots = np.zeros((xyz.shape[0], len(rot_names)))
  for idx, attr_name in enumerate(rot_names):
    rots[:, idx] = np.asarray(plydata.elements[0][attr_name])
  
  return SplatData(
    xyz = xyz,
    features_dc = features_dc,
    features_rest = features_extra,
    opacity = opacities,
    scaling = scales,
    rotation = rots,
    active_sh_degree = max_sh_degree
  )

def save_ply(path, data: SplatData):
  mkdirs(os.path.dirname(path))

  xyz = data.xyz
  normals = np.zeros_like(xyz)
  f_dc = data.features_dc.reshape(data.features_dc.shape[:1] + (-1,))
  f_rest = data.features_rest.reshape(data.features_rest.shape[:1] + (-1,))
  opacities = data.opacity
  scale = data.scaling
  rotation = data.rotation

  dtype_full = [(attribute, 'f4') for attribute in construct_list_of_attributes(data)]

  elements = np.empty(xyz.shape[0], dtype=dtype_full)
  attributes = np.concatenate((xyz, normals, f_dc, f_rest, opacities, scale, rotation), axis=1)
  elements[:] = list(map(tuple, attributes))
  el = PlyElement.describe(elements, 'vertex')
  PlyData([el]).write(path)

def save_splat(path, data: SplatData):
  # preprocess
  sorted_indices = np.argsort(
    -np.exp(np.sum(data.scaling, axis=-1)) / (1 + np.exp(-data.opacity.reshape((-1,))))
  )
  SH_C0 = 0.28209479177387814
  rgb = (0.5 + SH_C0 * data.features_dc).reshape((-1, 3))
  alpha = 1 / (1 + np.exp(-data.opacity)).reshape((-1, 1))
  color = np.concatenate((rgb, alpha), axis=-1).astype(np.float32)
  position = data.xyz.astype(np.float32)
  scale = np.exp(data.scaling).astype(np.float32)
  rotation = data.rotation.astype(np.float32)
  rotation = rotation / np.linalg.norm(rotation, axis=-1, keepdims=True)
  # quantize
  color = (color * 255).clip(0, 255).astype(np.uint8)
  rotation = (rotation * 128 + 128).clip(0, 255).astype(np.uint8)

  buffer = BytesIO()
  for idx in sorted_indices:
    buffer.write(position[idx].tobytes())
    buffer.write(scale[idx].tobytes())
    buffer.write(color[idx].tobytes())
    buffer.write(rotation[idx].tobytes())

  with open(path, "wb") as f:
    f.write(buffer.getvalue())

def main():
  args = get_args()

  assert os.path.isfile(args.input), f"File not exist: {args.input}"

  # Use input file with _rotated suffix as output if not specified
  if args.output is not None:
    output_path = args.output
  else:
    # Replace extension with _rotated.ply
    base, _ = os.path.splitext(args.input)
    output_path = base + '_rotated.ply'

  print(f':: Load splats from: {args.input}')

  data = load_ply(args.input, args.max_sh_degree)

  print(f':: Loaded splats: {data.xyz.shape[0]}')

  if args.enable_transform:
    data = transform_data(args, data)

  ext = os.path.splitext(output_path)[-1]

  print(f':: Save splats to: {output_path}')
  if ext == '.ply':
    save_ply(output_path, data)
  elif ext == '.splat':
    save_splat(output_path, data)
  else:
    raise NotImplementedError(ext)


if __name__ == '__main__':
  main()