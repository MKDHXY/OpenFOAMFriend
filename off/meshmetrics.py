"""Measure actual ASCII polyMesh: wall-normal distance and uniform-U CFL rate."""
from pathlib import Path
import re,json
import numpy as np
from .quality import audit,body

def measure(case,skew_limit=.5,nonortho_limit=30):
    import hashlib,uuid,os
    case=Path(case); root=case/'constant/polyMesh'; digest=hashlib.sha256()
    for name in ('points','faces','owner','neighbour','boundary'): digest.update((root/name).read_bytes())
    fingerprint=digest.hexdigest(); cache=case/'off_setup_metrics.json'
    if cache.exists():
        try:
            cached=json.loads(cache.read_text(encoding='utf-8'))
            if cached['mesh_sha256']==fingerprint and cached.get('thresholds')==[skew_limit,nonortho_limit]: return cached['quality'],cached['metrics']
        except (ValueError,KeyError): pass
    quality,points,faces,fc,_,_=audit(case,skew_limit,nonortho_limit)
    quality['count_thresholds']={'skewness':skew_limit,'nonorthogonality_deg':nonortho_limit}
    with np.load(case/'off_quality.npz') as arrays:
        cc=arrays['cell_centres'].copy(); owner=arrays['owner'].copy(); neighbour=arrays['neighbour'].copy(); volumes=arrays['volumes'].copy()
    areas=np.zeros((len(faces),3))
    for i,ids in enumerate(faces):
        poly=points[ids]; areas[i]=np.cross(poly,np.roll(poly,-1,axis=0)).sum(axis=0)/2
    flux=np.abs(areas[:,0]); total=np.bincount(owner,weights=flux,minlength=len(cc)); total+=np.bincount(neighbour,weights=flux[:len(neighbour)],minlength=len(cc))
    rate=float(np.max(total/(2*volumes))) if np.all(volumes>0) else None
    boundary=(case/'constant/polyMesh/boundary').read_text(encoding='utf-8'); block=re.search(r'\bcylinder\s*\{([^}]+)\}',boundary,re.S)
    wall=None
    if block:
        count=int(re.search(r'\bnFaces\s+(\d+)',block[1])[1]); start=int(re.search(r'\bstartFace\s+(\d+)',block[1])[1]); ids=np.arange(start,start+count)
        normals=areas[ids]/np.linalg.norm(areas[ids],axis=1)[:,None]; distance=np.abs(np.einsum('ij,ij->i',cc[owner[ids]]-fc[ids],normals))
        wall={'min_m':float(distance.min()),'max_m':float(distance.max()),'mean_m':float(distance.mean()),'faces':count,'definition':'Normal projection from owner volume centroid to cylinder face plane; geometric distance, not y+.'}
    metrics={'cells':quality['cells'],'wall_cell_distance':wall,'uniform_flux_rate_per_velocity':rate,'definition':'max_cells(sum_faces |(1,0,0) dot Sf| / (2 V)); multiply by U and dt for a uniform-inlet geometric Co estimate. Actual evolved-flow Co differs.','source_case':str(case)}
    metrics['mesh_sha256']=fingerprint
    temporary=cache.with_suffix('.'+uuid.uuid4().hex+'.tmp'); temporary.write_text(json.dumps({'mesh_sha256':fingerprint,'thresholds':[skew_limit,nonortho_limit],'quality':quality,'metrics':metrics},indent=2),encoding='utf-8'); os.replace(temporary,cache)
    return quality,metrics
