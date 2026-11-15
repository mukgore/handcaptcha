"""Sampled triangle-surface intersections, not anatomy or volume penetration.

Independent SAT implementation following Eberly, Method of Separating Axes,
Sec.9 (two triangles in 3D), including in-plane axes for coplanar triangles.
https://www.geometrictools.com/Documentation/MethodOfSeparatingAxes.pdf
Shared-vertex pairs are excluded and counted; their nonlocal overlap is NOT
checked. No continuous collision, signed volume, object physics or admission.
"""
import numpy as np

VERSION='sampled_triangle_sat_shared_vertex_excluded_v1'
RELATIVE_EPSILON=1e-7  # Numeric diagnostic tolerance, not anatomical clearance.


def triangle_pairs(a,b,epsilon):
    a=np.asarray(a,float);b=np.asarray(b,float)
    if a.shape!=b.shape or a.ndim!=3 or a.shape[1:]!=(3,3) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Matching finite triangle batches required')
    if type(epsilon) not in (int,float) or not 0<epsilon<=1e-3:
        raise ValueError('Explicit bounded numeric epsilon required')
    ea=np.roll(a,-1,axis=1)-a;eb=np.roll(b,-1,axis=1)-b
    na=np.cross(ea[:,0],ea[:,1]);nb=np.cross(eb[:,0],eb[:,1])
    la=np.linalg.norm(na,axis=1);lb=np.linalg.norm(nb,axis=1)
    if (la<=1e-14).any() or (lb<=1e-14).any():raise ValueError('Nondegenerate triangles required')
    na/=la[:,None];nb/=lb[:,None]
    axes=np.concatenate((na[:,None],nb[:,None],
        np.cross(ea[:,:,None],eb[:,None,:]).reshape(-1,9,3),
        np.cross(na[:,None],ea),np.cross(nb[:,None],eb)),axis=1)
    norms=np.linalg.norm(axes,axis=2);valid=norms>1e-14
    axes=axes/np.where(valid,norms,1.)[:,:,None]
    # Common local origin reduces translation cancellation for the projections.
    origin=a[:,0:1];pa=np.einsum('nvc,nac->nav',a-origin,axes);pb=np.einsum('nvc,nac->nav',b-origin,axes)
    separated=((pa.max(axis=2)<pb.min(axis=2)-epsilon)|(pb.max(axis=2)<pa.min(axis=2)-epsilon))&valid
    intersects=~separated.any(axis=1)
    da=np.einsum('nvc,nc->nv',a-b[:,0:1],nb)
    db=np.einsum('nvc,nc->nv',b-a[:,0:1],na)
    coplanar=(np.abs(da).max(axis=1)<=epsilon)&(np.abs(db).max(axis=1)<=epsilon)
    straddles=(da.min(axis=1)<-epsilon)&(da.max(axis=1)>epsilon)&(db.min(axis=1)<-epsilon)&(db.max(axis=1)>epsilon)
    return {'intersects':intersects,'coplanar_overlap':intersects&coplanar,
        'two_plane_straddling_indicator':intersects&straddles,
        'touch_or_numerically_ambiguous':intersects&~coplanar&~straddles}


def topology(faces,vertex_count):
    raw=np.asarray(faces)
    if (raw.dtype.kind not in 'iu' or raw.ndim!=2 or raw.shape[1]!=3 or not 1<=len(raw)<=2000
            or type(vertex_count) is not int or not 3<=vertex_count<=10000
            or raw.min()<0 or raw.max()>=vertex_count):
        raise ValueError('Bounded integer mesh topology required')
    f=raw.astype(np.int32)
    if any((f[:,a]==f[:,b]).any() for a,b in ((0,1),(0,2),(1,2))):raise ValueError('Repeated vertex within face')
    if len(np.unique(np.sort(f,axis=1),axis=0))!=len(f):raise ValueError('Duplicate faces are not valid distinct topology')
    i,j=np.triu_indices(len(f),1)
    shared=(f[i,:,None]==f[j,None,:]).any(axis=(1,2))
    edges=np.concatenate((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]))
    _,counts=np.unique(np.sort(edges,axis=1),axis=0,return_counts=True)
    return {'faces':f,'vertex_count':vertex_count,'pair_i':i[~shared].astype(np.int32),
        'pair_j':j[~shared].astype(np.int32),'shared_vertex_pairs_excluded_n':int(shared.sum()),
        'all_face_pairs_n':len(i),'boundary_edges_n':int((counts==1).sum()),
        'nonmanifold_edges_n':int((counts>2).sum()),'unused_vertices_n':vertex_count-len(np.unique(f))}


def frame(vertices,mesh,*,relative_epsilon=RELATIVE_EPSILON):
    v=np.asarray(vertices)
    if v.dtype.kind not in 'fiu' or v.shape!=(mesh['vertex_count'],3) or not np.isfinite(v).all():
        raise ValueError('Finite complete mesh coordinates required')
    if type(relative_epsilon) not in (int,float) or not 1e-12<=relative_epsilon<=1e-5:
        raise ValueError('Locked diagnostic relative tolerance required')
    v=v.astype(float);lo=v.min(axis=0);hi=v.max(axis=0);scale=float(np.linalg.norm(hi-lo))
    if not 1e-12<scale<1e6:raise ValueError('Nondegenerate bounded mesh extent required')
    v=(v-(lo+hi)/2)/scale;tri=v[mesh['faces']]
    edges=np.roll(tri,-1,axis=1)-tri
    area2=np.linalg.norm(np.cross(edges[:,0],edges[:,1]),axis=1)
    longest=np.linalg.norm(edges,axis=2).max(axis=1)
    degenerate=np.flatnonzero(area2<=relative_epsilon*np.maximum(longest,1e-30))
    base={'version':VERSION,'scope':'sampled_non_shared_vertex_triangle_surface_test_only',
        'faces_n':len(tri),'all_face_pairs_n':mesh['all_face_pairs_n'],
        'shared_vertex_pairs_excluded_n':mesh['shared_vertex_pairs_excluded_n'],
        'boundary_edges_n':mesh['boundary_edges_n'],'nonmanifold_edges_n':mesh['nonmanifold_edges_n'],
        'relative_numeric_epsilon':relative_epsilon,'native_numeric_epsilon':scale*relative_epsilon,
        'biological_validity_proven':False,'volume_penetration_free_proven':False,
        'continuous_collision_free_proven':False,'release_allowed':False}
    if len(degenerate):return {**base,'state':'UNMEASURABLE_DEGENERATE_TRIANGLES',
        'degenerate_face_ids':degenerate.tolist(),'tested_pairs_n':0,'pair_ids':{},'sampled_surface_clear':False}
    lower=tri.min(axis=1);upper=tri.max(axis=1);i=mesh['pair_i'];j=mesh['pair_j']
    broad=((lower[i]<=upper[j]+relative_epsilon)&(lower[j]<=upper[i]+relative_epsilon)).all(axis=1)
    i=i[broad];j=j[broad]
    if len(i)>200000:raise ValueError('Triangle narrow-phase budget exceeded; no success assumed')
    result=triangle_pairs(tri[i],tri[j],relative_epsilon) if len(i) else {
        key:np.zeros(0,bool) for key in ('intersects','coplanar_overlap','two_plane_straddling_indicator','touch_or_numerically_ambiguous')}
    pairs={key:np.column_stack((i[mask],j[mask])).tolist() for key,mask in result.items()}
    return {**base,'state':'SURFACE_INTERSECTION_INDICATORS' if result['intersects'].any() else 'NO_TESTED_PAIR_INTERSECTION',
        'degenerate_face_ids':[],'tested_pairs_n':len(i),'pair_ids':pairs,
        'sampled_surface_clear':not bool(result['intersects'].any())}
