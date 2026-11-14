"""Analytic orthographic capsule/sphere surface visibility for private QA.

Camera is at +Z looking toward -Z; largest surface Z wins. No palm mesh,
cast shadows, reflections, anatomy, force closure or photorealism claim.
"""
import math

import cv2
import numpy as np

from dataset_pipeline.common import LANDMARK_NAMES
from .contact import EDGES
from .generate import WIDTH, HEIGHT, SCALE
from .grasp_contacts import RADIUS

VERSION = 'authored_capsule_sphere_orthographic_surface_v1'
MODES = ('flat_object', 'lit_object', 'flat_hand_only', 'lit_hand_only')
OBJECT_ID = len(EDGES) + 1
TARGET_IDS = tuple(i+1 for i, edge in enumerate(EDGES) if edge in ((9, 10), (10, 11)))
LIGHT = np.array([-.4, .6, 1.]); LIGHT /= np.linalg.norm(LIGHT)


def _point(value):
    point = np.asarray(value, dtype=float)
    if point.shape != (3,) or not np.isfinite(point).all() or np.max(np.abs(point)) > 10:
        raise ValueError('Finite bounded authored coordinates required')
    return point


def _radius(value):
    if type(value) not in (float, int) or not math.isfinite(value) or not 1e-4 <= value <= 2:
        raise ValueError('Bounded positive authored surface radius required')
    return float(value)


def sphere_surface(x, y, center, radius):
    """Front intersection of orthographic rays and an opaque sphere."""
    center = _point(center); radius = _radius(radius)
    dx, dy = x-center[0], y-center[1]
    discriminant = radius*radius-dx*dx-dy*dy; hit = discriminant >= 0
    dz = np.sqrt(np.maximum(0., discriminant))
    depth = np.where(hit, center[2]+dz, -np.inf)
    normals = np.stack((dx+np.zeros_like(dz), dy+np.zeros_like(dz), dz), axis=-1)/radius
    normals[~hit] = 0.
    return depth, normals


def capsule_surface(x, y, a, b, radius):
    """Union of finite cylinder and endpoint spheres; choose nearest hit."""
    a, b, radius = _point(a), _point(b), _radius(radius)
    length = float(np.linalg.norm(b-a))
    if length <= 1e-10: raise ValueError('Nondegenerate capsule axis required')
    direction = (b-a)/length
    depth, normals = sphere_surface(x, y, a, radius)
    end_depth, end_normals = sphere_surface(x, y, b, radius)
    nearer = end_depth > depth
    depth[nearer] = end_depth[nearer]; normals[nearer] = end_normals[nearer]
    # |(I-dd^T)(q+t*z_axis)|^2 = r^2 for q=(x-ax,y-ay,0).
    dx, dy = x-a[0], y-a[1]; along = dx*direction[0]+dy*direction[1]
    aa = float(direction[0]**2+direction[1]**2)
    if aa > 1e-14:
        bb = -2*along*direction[2]
        cc = dx*dx+dy*dy-along*along-radius*radius
        disc = bb*bb-4*aa*cc; root = np.sqrt(np.maximum(0., disc))
        for t in ((-bb+root)/(2*aa), (-bb-root)/(2*aa)):
            projection = along+t*direction[2]
            z = a[2]+t
            valid = (disc >= 0) & (projection >= 0) & (projection <= length) & (z > depth)
            normal = np.stack((dx-projection*direction[0], dy-projection*direction[1],
                               t-projection*direction[2]), axis=-1)/radius
            depth[valid] = z[valid]; normals[valid] = normal[valid]
    return depth, normals


class Surface:
    def __init__(self):
        self.depth = np.full((HEIGHT, WIDTH), -np.inf)
        self.normals = np.zeros((HEIGHT, WIDTH, 3))
        self.owner = np.zeros((HEIGHT, WIDTH), np.uint8)

    def add(self, points, radius, identifier):
        points = [_point(p) for p in points]; radius = _radius(radius)
        if len(points) not in (1, 2) or type(identifier) is not int or not 1 <= identifier <= OBJECT_ID:
            raise ValueError('Known opaque primitive required')
        bounds = np.asarray(points)
        x0 = max(0, math.floor(256+SCALE*(bounds[:, 0].min()-radius)))
        x1 = min(WIDTH, math.ceil(256+SCALE*(bounds[:, 0].max()+radius))+1)
        y0 = max(0, math.floor(220-SCALE*(bounds[:, 1].max()+radius)))
        y1 = min(HEIGHT, math.ceil(220-SCALE*(bounds[:, 1].min()-radius))+1)
        if x1 <= x0 or y1 <= y0: return
        yy, xx = np.mgrid[y0:y1, x0:x1]
        x, y = (xx-256)/SCALE, (220-yy)/SCALE
        z, normal = (sphere_surface(x, y, points[0], radius) if len(points) == 1 else
                     capsule_surface(x, y, points[0], points[1], radius))
        region = np.s_[y0:y1, x0:x1]; update = z > self.depth[region]+1e-10
        self.depth[region][update] = z[update]
        self.normals[region][update] = normal[update]
        self.owner[region][update] = identifier

    def image(self, *, lit):
        if type(lit) is not bool: raise ValueError('Explicit flat/lit mode required')
        image = np.full((HEIGHT, WIDTH, 3), (40, 32, 24), np.uint8)
        visible = self.owner != 0; obj = self.owner == OBJECT_ID
        colors = np.empty_like(image); colors[:] = (160, 196, 220); colors[obj] = (80, 190, 100)
        shade = .35+.65*np.maximum(0., self.normals@LIGHT) if lit else np.ones_like(self.depth)
        image[visible] = np.clip(np.rint(colors[visible]*shade[visible, None]), 0, 255).astype(np.uint8)
        cv2.putText(image, 'SURFACE PROXY / NOT HUMAN VALIDATION', (12, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, .46, (220, 220, 220), 1, cv2.LINE_AA)
        return image


def render(frame):
    points = np.array([_point([frame['landmarks_world'][name][axis] for axis in ('x', 'y', 'z')])
                       for name in LANDMARK_NAMES])
    for name, point in zip(LANDMARK_NAMES, points):
        px = frame['landmarks_px'][name]
        if any(type(px[a]) not in (int, float) or not math.isfinite(px[a]) for a in ('x', 'y', 'z')):
            raise ValueError('Finite matching projection required')
        if not np.allclose([px['x'], px['y'], px['z']], [256+SCALE*point[0], 220-SCALE*point[1], point[2]], rtol=0, atol=1e-9):
            raise ValueError('Image/world projection mismatch')
        if not 0 <= px['x'] < WIDTH or not 0 <= px['y'] < HEIGHT:
            raise ValueError('Authored landmarks leave viewport')
    surface = Surface()
    for i, (a, b) in enumerate(EDGES): surface.add([points[a], points[b]], RADIUS, i+1)
    images = {'flat_hand_only': surface.image(lit=False), 'lit_hand_only': surface.image(lit=True)}
    hand_owner = surface.owner.copy()
    obj = frame['authored_object']
    if obj['kind'] != 'kinematic_sphere': raise ValueError('Known authored object required')
    surface.add([obj['center']], obj['radius'], OBJECT_ID)
    images.update({'flat_object': surface.image(lit=False), 'lit_object': surface.image(lit=True)})
    return {'images': images, 'owner': surface.owner, 'hand_only_owner': hand_owner,
            'depth': surface.depth, 'normals': surface.normals}
