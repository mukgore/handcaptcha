"""Authored sphere-touch fixture with explicit capsule proxy checks.

Units and radii are engineering parameters, not anatomical measurements.
This checks a bone-capsule/sphere proxy only, not hand meshes or physics.
"""
import math
import numpy as np

from dataset_pipeline.common import LANDMARK_NAMES

EDGES = [(0, base) for base in (1, 5, 9, 13, 17)] + [
    (base + j, base + j + 1) for base in (1, 5, 9, 13, 17) for j in range(3)]
CAPSULE_RADIUS = .025
OBJECT_RADIUS = .10
CONTACT_TOLERANCE = .003


def segment_distance(point, start, end):
    point, start, end = (np.asarray(x, dtype=float) for x in (point, start, end))
    if any(x.shape != (3,) or not np.isfinite(x).all() for x in (point, start, end)):
        raise ValueError('Finite 3D points required')
    vector = end - start; square = float(vector @ vector)
    if square <= 1e-16:
        raise ValueError('Degenerate bone segment')
    alpha = float(np.clip((point - start) @ vector / square, 0., 1.))
    return float(np.linalg.norm(point - (start + alpha * vector)))


def points(frame):
    return np.array([[frame['landmarks_world'][name][axis] for axis in ('x', 'y', 'z')]
                     for name in LANDMARK_NAMES], dtype=float)


def inspect(records, sphere, *, capsule_radius=CAPSULE_RADIUS, tolerance=CONTACT_TOLERANCE):
    if not records:
        raise ValueError('Every planned frame must be present')
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) or x <= 0
           for x in (capsule_radius, tolerance, sphere['radius'])):
        raise ValueError('Finite positive proxy parameters required')
    center = np.asarray(sphere['center'], dtype=float)
    minimum = math.inf; contacts = []; bad = []; lengths = None; gaps = []
    for index, frame in enumerate(records):
        if frame['frame_idx'] != index:
            raise ValueError('Complete ordered frame denominator required')
        p = points(frame)
        distances = [segment_distance(center, p[a], p[b]) - sphere['radius'] - capsule_radius for a, b in EDGES]
        current = np.array([np.linalg.norm(p[b] - p[a]) for a, b in EDGES])
        if lengths is None: lengths = current
        if not np.allclose(current, lengths, rtol=0, atol=1e-10):
            raise ValueError('Bone lengths changed')
        minimum = min(minimum, min(distances))
        if min(distances) < -1e-9: bad.append(index)
        gap = float(np.linalg.norm(p[12] - center) - sphere['radius'] - capsule_radius)
        gaps.append(gap)
        if abs(gap) <= tolerance: contacts.append(index)
    approach_retreat = bool(contacts and 0 < contacts[0] <= contacts[-1] < len(records) - 1
                           and gaps[0] > tolerance * 3 and gaps[-1] > tolerance * 3)
    return {'schema_version': 1, 'proxy': 'fixed_bone_capsules_vs_static_sphere',
            'planned_frames': len(records), 'checked_frames': len(records),
            'penetrating_frames': bad, 'minimum_clearance': minimum,
            'contact_frames': contacts, 'target_landmark': 'MIDDLE_TIP',
            'approach_contact_retreat': approach_retreat,
            'accepted': not bad and approach_retreat, 'capsule_radius': capsule_radius,
            'contact_tolerance': tolerance, 'release_allowed': False,
            'limitations': ['no mesh or palm surface collision', 'no self-collision check',
                            'no grasp dynamics or anatomical/human validation']}


def generate_touch(seed, frames=24, fps=12.):
    from .generate import generate_motion
    records = generate_motion('middle_flex', seed, frames, fps)
    peak = max(range(frames), key=lambda i: points(records[i])[12, 2])
    center = points(records[peak])[12] + [0., 0., OBJECT_RADIUS + CAPSULE_RADIUS]
    sphere = {'kind': 'static_sphere', 'center': center.tolist(), 'radius': OBJECT_RADIUS,
              'units': 'authored_engineering_units'}
    report = inspect(records, sphere)
    for frame in records: frame['authored_object'] = sphere
    return records, sphere, report
