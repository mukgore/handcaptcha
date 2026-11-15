"""BMC geometric features from 21 points, independently implemented for QA.

Spurr et al., ECCV 2020, main Sec.3.1 Eq.1-6 and supplement Sec.1 Eq.2.
https://jankautz.com/publications/WeaklySupervised3DHand_ECCV20.pdf
No learned limits/network or anatomical-validity guarantee is supplied.
Frames are column bases; singular geometry is rejected, never epsilon-filled.
"""
import math

import numpy as np

from dataset_pipeline.common import LANDMARK_NAMES

VERSION='bmc21_column_frames_signed_angles_v1'
BASES=(1,5,9,13,17)
BONE_LABELS=tuple(LANDMARK_NAMES[b] for b in BASES)+tuple(LANDMARK_NAMES[b+j] for b in BASES for j in (1,2,3))
ANGLE_RECORD_VERSION='bmc_angle_center_child_and_clinical_candidate_v1'
ANGLE_CHILD_LABELS=tuple(LANDMARK_NAMES[b+j] for b in BASES for j in (1,2,3))
# An angle rotates the outgoing bone at its parent/center, not at its child.
JOINT_LABELS=tuple(LANDMARK_NAMES[b+j-1] for b in BASES for j in (1,2,3))
ANGLE_RECORDS=tuple({'angle_index':3*finger+j-1,
    'canonical_center_point':LANDMARK_NAMES[b+j-1],
    'incoming_bone_parent_point':LANDMARK_NAMES[0 if j==1 else b+j-2],
    'outgoing_bone_child_point':LANDMARK_NAMES[b+j],
    'candidate_clinical_joint':(('TMC','MCP','IP') if finger==0 else ('MCP','PIP','DIP'))[j-1],
    'clinical_axes_neutral_and_sign_verified':False}
    for finger,b in enumerate(BASES) for j in (1,2,3))


class GeometryError(ValueError):
    def __init__(self, code):
        self.code=code;super().__init__(code)


def unit(vector, code):
    vector=np.asarray(vector,float);length=float(np.linalg.norm(vector))
    if not math.isfinite(length) or length<=1e-10:raise GeometryError(code)
    return vector/length


def rotation(flexion,abduction):
    """Ry(flexion) Rx(-abduction), expressed in the parent column basis."""
    f,a=flexion,abduction
    y=np.array([[math.cos(f),0.,math.sin(f)],[0.,1.,0.],[-math.sin(f),0.,math.cos(f)]])
    x=np.array([[1.,0.,0.],[0.,math.cos(a),math.sin(a)],[0.,-math.sin(a),math.cos(a)]])
    return y@x


def signed_angles(local_bone):
    b=unit(local_bone,'DEGENERATE_FINGER_BONE')
    projected=math.hypot(b[0],b[2])
    if projected<=1e-10:raise GeometryError('UNDEFINED_FLEXION_AT_ABDUCTION_POLE')
    # Equivalent to the supplement's octant-resolved angle convention.
    return np.array([math.atan2(b[0],b[2]),math.atan2(b[1],projected)])


def extract(points, *, handedness):
    raw=np.asarray(points)
    if raw.shape!=(21,3) or raw.dtype.kind not in 'fiu':raise ValueError('21 numeric 3D points required')
    p=raw.astype(float)
    if not np.isfinite(p).all() or np.max(np.abs(p))>1e6:raise ValueError('Finite bounded world coordinates required')
    if handedness not in ('right','left'):raise ValueError('Explicit handedness convention required')
    p=p-p[0]
    if handedness=='left':p[:,0]*=-1
    roots=p[list(BASES)];root_units=np.array([unit(b,'DEGENERATE_ROOT_BONE') for b in roots])
    bones=np.array(list(roots)+[p[b+j]-p[b+j-1] for b in BASES for j in (1,2,3)])
    lengths=np.linalg.norm(bones,axis=1)
    if (lengths<=1e-10).any():raise GeometryError('DEGENERATE_BONE')
    normals=np.array([unit(np.cross(root_units[i+1],root_units[i]),'DEGENERATE_PALM_TRIANGLE') for i in range(4)])
    edges=np.array([normals[0],unit(normals[0]+normals[1],'CANCELLING_PALM_EDGE_NORMALS'),
        unit(normals[1]+normals[2],'CANCELLING_PALM_EDGE_NORMALS'),
        unit(normals[2]+normals[3],'CANCELLING_PALM_EDGE_NORMALS'),normals[3]])
    differences=np.diff(roots,axis=0)
    curvature=np.array([float((edges[i+1]-edges[i])@unit(differences[i],'DEGENERATE_ROOT_SEPARATION')) for i in range(4)])
    spread=np.arccos(np.clip(np.sum(root_units[:-1]*root_units[1:],axis=1),-1.,1.))
    first_x=[-normals[0],-normals[1],-edges[2],-edges[3],-normals[3]]
    angles=[];frames=[]
    for index,base in enumerate(BASES):
        z=root_units[index];x=unit(first_x[index],'DEGENERATE_LOCAL_X')
        y=unit(np.cross(z,x),'DEGENERATE_LOCAL_Y');frame=np.column_stack((x,y,z))
        if not np.allclose(frame.T@frame,np.eye(3),rtol=0,atol=1e-9) or np.linalg.det(frame)<0:
            raise GeometryError('NON_ORTHONORMAL_PALM_BASIS')
        for j in (1,2,3):
            bone=unit(p[base+j]-p[base+j-1],'DEGENERATE_FINGER_BONE')
            pair=signed_angles(frame.T@bone);angles.append(pair);frames.append(frame.copy())
            frame=frame@rotation(*pair)
            if not np.allclose(frame[:,2],bone,rtol=0,atol=1e-9):
                raise GeometryError('LOCAL_FRAME_RECONSTRUCTION_MISMATCH')
    return {'feature_version':VERSION,'bone_lengths':lengths,'palm_curvatures':curvature,
            'palm_spread_radians':spread,'joint_angles_radians':np.array(angles),'local_frames':np.array(frames),
            'angle_record_version':ANGLE_RECORD_VERSION,'joint_angle_records':[dict(r) for r in ANGLE_RECORDS],
            'angle_representation':'signed_radians_in_BMC_column_frames_not_verified_clinical_MDH_angles'}


def angular_derivatives(angles,times):
    angles=np.asarray(angles,float);times=np.asarray(times,float)
    if angles.ndim!=3 or angles.shape[1:]!=(15,2) or len(angles)<3 or times.shape!=(len(angles),) or not np.isfinite(angles).all() or not np.isfinite(times).all() or (np.diff(times)<=0).any():
        raise ValueError('At least three complete angle frames with increasing seconds required')
    continuous=angles.copy();continuous[:,:,0]=np.unwrap(continuous[:,:,0],axis=0)
    dt=np.diff(times);velocity=np.diff(continuous,axis=0)/dt[:,None,None]
    acceleration=np.diff(velocity,axis=0)/((dt[:-1]+dt[1:])/2)[:,None,None]
    if not np.isfinite(velocity).all() or not np.isfinite(acceleration).all():
        raise ValueError('Unrepresentable angular derivatives')
    return velocity,acceleration
