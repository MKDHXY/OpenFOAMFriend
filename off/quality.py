"""Per-face OpenFOAM-14 skewness/non-orthogonality with real locations.

Formula source: OpenFOAM-14/src/meshCheck/primitiveMeshCheck/primitiveMeshCheck.C
Geometric centres are volume/area-weighted, not bounding-box centres.
"""
import re, json
from pathlib import Path
import numpy as np

def body(path):
    s=Path(path).read_text(errors='strict')
    if re.search(r'format\s+binary',s): raise ValueError('Quality location parser needs ASCII polyMesh. Convert with foamFormatConvert first.')
    s=re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
    m=re.search(r'\}\s*(\d+)\s*\(',s)
    if not m: raise ValueError('Cannot read OpenFOAM list: '+str(path))
    return int(m[1]),s[m.end():]

def audit(case,skew_limit=0.5,nonortho_limit=30):
    root=Path(case)/'constant'/'polyMesh'
    n,s=body(root/'points'); points=np.array([[float(v) for v in t.split()] for t in re.findall(r'\(([^()]+)\)',s)[:n]])
    nf,s=body(root/'faces'); faces=[np.array(list(map(int,x.split()))) for x in re.findall(r'\d+\s*\(([^()]*)\)',s)[:nf]]
    n,s=body(root/'owner'); owner=np.array(list(map(int,re.findall(r'\d+',s)[:n])))
    ni,s=body(root/'neighbour'); nei=np.array(list(map(int,re.findall(r'\d+',s)[:ni])))
    nc=int(owner.max()+1); reference=points.mean(axis=0)
    fc=np.zeros((nf,3)); fa=np.zeros((nf,3)); volumes=np.zeros(nc); moments=np.zeros((nc,3))
    for i,ids in enumerate(faces):
        poly=points[ids]; centre=poly.mean(axis=0); area=0; sumc=np.zeros(3)
        for k in range(len(poly)):
            a=poly[k]; b=poly[(k+1)%len(poly)]
            av=np.cross(a-centre,b-centre)/2; mag=np.linalg.norm(av)
            fa[i]+=av; area+=mag; sumc+=mag*(centre+a+b)/3
            cr=centre-reference; ar=a-reference; br=b-reference
            vol=np.dot(cr,np.cross(ar,br))/6; moment=vol*(cr+ar+br)/4
            volumes[owner[i]]+=vol; moments[owner[i]]+=moment
            if i<ni: volumes[nei[i]]-=vol; moments[nei[i]]-=moment
        fc[i]=sumc/max(area,1e-300)
    cc=reference+moments/volumes[:,None]
    skew=np.zeros(nf); angles=np.zeros(nf)
    for i,ids in enumerate(faces):
        cpf=fc[i]-cc[owner[i]]
        if i<ni: d=cc[nei[i]]-cc[owner[i]]
        else:
            normal=fa[i]/max(np.linalg.norm(fa[i]),1e-300); d=normal*np.dot(normal,cpf)
        den=np.dot(fa[i],d); sv=cpf-d*np.dot(fa[i],cpf)/max(den,1e-300)
        mag=np.linalg.norm(sv); unit=sv/max(mag,1e-300)
        fd=max((.2 if i<ni else .4)*np.linalg.norm(d),np.max(np.abs((points[ids]-fc[i])@unit)),1e-300)
        skew[i]=mag/fd
        if i<ni: angles[i]=np.degrees(np.arccos(np.clip(den/max(np.linalg.norm(d)*np.linalg.norm(fa[i]),1e-300),-1,1)))
    worst_skew=int(np.argmax(skew)); worst_angle=int(np.argmax(angles[:ni]))
    result={'cells':nc,'faces':nf,'internal_faces':ni,'max_skewness':float(skew[worst_skew]),'max_nonorthogonality_deg':float(angles[worst_angle]),'skew_above_limit':int(np.sum(skew>skew_limit)), 'nonortho_above_limit':int(np.sum(angles[:ni]>nonortho_limit)),'min_cell_volume':float(volumes.min()),'nonpositive_cells':int(np.sum(volumes<=0)), 'worst_skew_face':worst_skew,'worst_skew_xyz':fc[worst_skew].tolist(),'worst_nonortho_face':worst_angle,'worst_nonortho_xyz':fc[worst_angle].tolist(),'source':'OpenFOAM-14 meshCheck formulas; independently calculated from ASCII polyMesh'}
    np.savez(Path(case)/'off_quality.npz',points=points,owner=owner,neighbour=nei,face_centres=fc,cell_centres=cc,skewness=skew,nonorthogonality=angles,volumes=volumes)
    (Path(case)/'off_quality.json').write_text(json.dumps(result,indent=2))
    return result,points,faces,fc,skew,angles
