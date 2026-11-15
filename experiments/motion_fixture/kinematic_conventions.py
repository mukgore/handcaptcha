"""Independent reference for selected BIO-07 DH and BIO-06 modified-DH tables.

Engineering lengths/poses and explicitly chosen local bases only. This is not
fitting a MANO rig or proving that clinical or BMC joint axes are equivalent.
Cobos2008 Tables I-II; Chen Chen2013 Tables7-8 + terminal tip translation.
"""
import math
import numpy as np

VERSION='published_dh_mdh_local_chain_reference_v1'


def rx(angle):
    c,s=math.cos(angle),math.sin(angle)
    return np.array([[1.,0.,0.,0.],[0.,c,-s,0.],[0.,s,c,0.],[0.,0.,0.,1.]])


def rz(angle):
    c,s=math.cos(angle),math.sin(angle)
    return np.array([[c,-s,0.,0.],[s,c,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]])


def tx(length):
    result=np.eye(4);result[0,3]=length;return result


def parameters(kind,angles,lengths):
    if kind not in ('nonthumb','thumb'):raise ValueError('Explicit chain kind required')
    q=np.asarray(angles,float);lengths=np.asarray(lengths,float)
    if q.shape!=((5,) if kind=='nonthumb' else (4,)) or lengths.shape!=((4,) if kind=='nonthumb' else (3,)):
        raise ValueError('Complete angle/length dimensions required')
    if not np.isfinite(q).all() or not np.isfinite(lengths).all() or (lengths<=0).any() or (lengths>1e6).any() or (np.abs(q)>2*math.pi).any():
        raise ValueError('Finite bounded engineering parameters required')
    return q,lengths


def chain(kind,angles,lengths,convention):
    q,l=parameters(kind,angles,lengths)
    if convention not in ('BIO07_standard_DH','BIO06_modified_DH'):raise ValueError('Explicit source convention required')
    standard=convention=='BIO07_standard_DH';transform=np.eye(4);positions=[np.zeros(3)]
    if kind=='nonthumb':
        a=[l[0],0.,l[1],l[2],l[3]] if standard else [0.,l[0],0.,l[1],l[2]]
        alpha=[math.pi/2,-math.pi/2,0.,0.,0.] if standard else [math.pi/2,-math.pi/2,math.pi/2,0.,0.]
        selected=(0,2,3,4) if standard else (1,3,4)
        names=['CMC','MCP','PIP','DIP','TIP']
    else:
        a=[0.,l[0],l[1],l[2]] if standard else [0.,0.,l[0],l[1]]
        alpha=[math.pi/2,0.,0.,0.] if standard else [0.,math.pi/2,0.,0.]
        selected=(1,2,3) if standard else (2,3)
        names=['TMC','MCP','IP','TIP']
    for i,(angle,distance,twist) in enumerate(zip(q,a,alpha)):
        transform=transform@(rz(angle)@tx(distance)@rx(twist) if standard else rx(twist)@tx(distance)@rz(angle))
        if i in selected:positions.append(transform[:3,3].copy())
    if not standard:
        transform=transform@tx(l[-1]);positions.append(transform[:3,3].copy())
    return {'points':np.array(positions),'point_names':names,'tip_transform':transform,
        'length_unit':'engineering_reference_units','local_origin':'finger_base_not_wrist',
        'anatomical_fit_verified':False}


def equivalent_modified_inputs(kind,standard_angles):
    q=np.asarray(standard_angles,float).copy()
    if kind=='nonthumb' and q.shape==(5,):
        q[1]*=-1;alignment=rx(-math.pi/2)
    elif kind=='thumb' and q.shape==(4,):alignment=np.eye(4)
    else:raise ValueError('Explicit complete standard-chain angles required')
    return q,alignment


def isolated_mcp_vector(abduction,flexion):
    # Standard DH nonthumb MCP after neutral CMC: Rx(pi/2)Rz(a)Rx(-pi/2)Rz(f).
    return (rx(math.pi/2)@rz(abduction)@rx(-math.pi/2)@rz(flexion))[:3,:3]@np.array([1.,0.,0.])


# Explicit chosen neutral basis for a single joint, NOT a measured hand frame:
# BMC x -> reference y, BMC y -> reference z, BMC z -> reference x.
ISOLATED_BMC_BASIS=np.array([[0.,0.,1.],[1.,0.,0.],[0.,1.,0.]])
