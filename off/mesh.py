"""Genuine blockMesh / Gmsh generation. No simulated mesh previews."""
import math
import threading
from pathlib import Path
from .models import Project

def header(name,cls='dictionary'):
    return f'FoamFile\n{{ format ascii; class {cls}; object {name}; }}\n'

def cylinder_dict(p: Project):
    p.validate(); s=p.shapes[0]; r=s['width']/2; R=p.outer_radius
    nz=p.spanwise if p.dimension==3 else 1; nq=p.circumferential//4
    xy=[(s['x']+a*radius,s['y']+b*radius) for radius in (r,R) for a,b in ((1,0),(0,1),(-1,0),(0,-1))]
    points=[(x,y,z) for z in (-p.depth/2,p.depth/2) for x,y in xy]
    blocks=[]; edges=[]; patches={'inlet':[],'outlet':[],'cylinder':[],'front':[],'back':[]}
    for i in range(4):
        j=(i+1)%4
        v=[i,i+4,j+4,j,i+8,i+12,j+12,j+8]
        blocks.append('hex ('+' '.join(map(str,v))+f') ({p.radial} {nq} {nz}) simpleGrading ({p.grading} 1 1)')
        patches['outlet' if i in (0,3) else 'inlet'].append((i+4,j+4,j+12,i+12))
        patches['cylinder'].append((j,i,i+8,j+8))
        patches['front'].append((i,j,j+4,i+4)); patches['back'].append((i+8,i+12,j+12,j+8))
        theta=(i+.5)*math.pi/2
        for k,radius in ((0,r),(4,R),(8,r),(12,R)):
            z=-p.depth/2 if k<8 else p.depth/2
            edges.append(f'arc {i+k} {j+k} ({s["x"]+radius*math.cos(theta):.12g} {s["y"]+radius*math.sin(theta):.12g} {z:.12g})')
    text=header('blockMeshDict')+'convertToMeters 1;\nvertices\n(\n'+''.join(f'({x:.12g} {y:.12g} {z:.12g})\n' for x,y,z in points)+');\nblocks\n(\n'+'\n'.join(blocks)+'\n);\nedges\n(\n'+'\n'.join(edges)+'\n);\nboundary\n(\n'
    for name,faces in patches.items():
        typ='wall' if name=='cylinder' else ('empty' if p.dimension==2 else 'symmetryPlane') if name in ('front','back') else 'patch'
        text+=name+' { type '+typ+'; faces ('+' '.join('('+' '.join(map(str,f))+')' for f in faces)+'); }\n'
    return text+');\nmergePatchPairs ();\n'

_gmsh_lock = threading.RLock()

def build_gmsh(p: Project,output: Path):
    # Gmsh's model is global. Concurrent Qt workers must not reset each other.
    with _gmsh_lock:
        return _build_gmsh(p, output)

def _build_gmsh(p: Project,output: Path):
    if p.mesh_method=='Manual topology (Gmsh)':
        from .manual_topology import build_gmsh as manual_gmsh
        p.validate(); return manual_gmsh(p,output)
    import gmsh
    p.validate(); gmsh.initialize(interruptible=False); gmsh.option.setNumber('General.Terminal',0)
    try:
        gmsh.model.add(p.name); occ=gmsh.model.occ
        surf=occ.addRectangle(p.xmin,p.ymin,0,p.xmax-p.xmin,p.ymax-p.ymin)
        holes=[]
        for s in p.shapes:
            if s['kind']=='circle': tag=occ.addDisk(s['x'],s['y'],0,s['width']/2,s['height']/2)
            elif s['kind']=='rectangle': tag=occ.addRectangle(s['x']-s['width']/2,s['y']-s['height']/2,0,s['width'],s['height'])
            elif s['kind'] in ('triangle','polygon'):
                from .geometry import vertices
                pts=[occ.addPoint(x,y,0) for x,y in vertices(s)]
                loop=occ.addCurveLoop([occ.addLine(pts[i],pts[(i+1)%len(pts)]) for i in range(len(pts))])
                tag=occ.addPlaneSurface([loop])
            else: raise ValueError('Unsupported shape '+s['kind'])
            holes.append((2,tag))
        result,_=occ.cut([(2,surf)],holes) if holes else ([(2,surf)],None)
        occ.synchronize()
        recombine=p.mesh_method in ('Gmsh quadrilateral / prism',)
        gmsh.option.setNumber('Mesh.MeshSizeMax',p.cell_size); gmsh.option.setNumber('Mesh.MeshSizeMin',min([p.cell_size]+[r['size']*min(1,r['ratio']) for r in p.regions]))
        gmsh.option.setNumber('Mesh.Smoothing',p.smoothing)
        gmsh.option.setNumber('Mesh.MeshSizeFromCurvature',24)
        fields=[]
        for r in p.regions:
            fid=gmsh.model.mesh.field.add('MathEval'); direction=r['direction']; ratio=r['ratio']
            from .grading import size_expression
            f=size_expression(r)
            blend=max(min(r['width'],r['height'])*.1,r['size'])
            weight=f'0.0625*(1+Tanh((x-({r["x"]}))/{blend}))*(1+Tanh((({r["x"]+r["width"]})-x)/{blend}))*(1+Tanh((y-({r["y"]}))/{blend}))*(1+Tanh((({r["y"]+r["height"]})-y)/{blend}))'
            gmsh.model.mesh.field.setString(fid,'F',f'{p.cell_size}+({weight})*(({r["size"]})*({f})-({p.cell_size}))'); fields.append(fid)
        if fields:
            fid=gmsh.model.mesh.field.add('Min'); gmsh.model.mesh.field.setNumbers(fid,'FieldsList',fields); gmsh.model.mesh.field.setAsBackgroundMesh(fid)
        if recombine:
            for _,tag in result: gmsh.model.mesh.setRecombine(2,tag)
        # Extruded 2D requires one cell and empty front/back in OpenFOAM.
        nz=p.spanwise if p.dimension==3 else 1
        tet=p.mesh_method=='Gmsh tetrahedral'
        out=occ.extrude(result,0,0,p.depth, numElements=[] if tet else [nz], recombine=not tet)
        occ.synchronize()
        groups={'inlet':[],'outlet':[],'farfield':[],'cylinder':[],'front':[],'back':[]}
        tol=max(p.xmax-p.xmin,p.ymax-p.ymin,p.depth)*1e-6
        for _,tag in gmsh.model.getEntities(2):
            b=gmsh.model.getBoundingBox(2,tag)
            if abs(b[2])<tol and abs(b[5])<tol: name='front'
            elif abs(b[2]-p.depth)<tol and abs(b[5]-p.depth)<tol: name='back'
            elif abs(b[0]-p.xmin)<tol and abs(b[3]-p.xmin)<tol: name='inlet'
            elif abs(b[0]-p.xmax)<tol and abs(b[3]-p.xmax)<tol: name='outlet'
            elif (abs(b[1]-p.ymin)<tol and abs(b[4]-p.ymin)<tol) or (abs(b[1]-p.ymax)<tol and abs(b[4]-p.ymax)<tol): name='farfield'
            else: name='cylinder'
            groups[name].append(tag)
        for name,tags in groups.items():
            if tags: gmsh.model.setPhysicalName(2,gmsh.model.addPhysicalGroup(2,tags),name)
        vols=[tag for dim,tag in out if dim==3]
        gmsh.model.setPhysicalName(3,gmsh.model.addPhysicalGroup(3,vols),'fluid')
        gmsh.option.setNumber('Mesh.MshFileVersion',2.2)
        if tet: gmsh.option.setNumber('Mesh.Algorithm3D',10)
        gmsh.model.mesh.generate(3)
        if tet: gmsh.model.mesh.optimize('Netgen')
        gmsh.write(str(output.with_suffix('.brep')))
        gmsh.write(str(output)); gmsh.write(str(output.with_suffix('.vtk')))
        return {'elements':sum(len(a) for a in gmsh.model.mesh.getElements(3)[1]),'mesh':str(output)}
    finally: gmsh.finalize()

def partitioned_box_dict(p):
    if p.shapes: raise ValueError('Structured partitioned box requires no obstacles. Use Gmsh for obstacle geometry or O-grid for a cylinder.')
    xs=sorted(set([p.xmin,p.xmax]+[v for r in p.regions for v in (r['x'],r['x']+r['width']) if p.xmin<v<p.xmax]))
    ys=sorted(set([p.ymin,p.ymax]+[v for r in p.regions for v in (r['y'],r['y']+r['height']) if p.ymin<v<p.ymax]))
    nx=len(xs); ny=len(ys); nz=p.spanwise if p.dimension==3 else 1
    # Shared grid lines propagate across the domain: neighbouring block faces
    # must have identical subdivisions and grading to remain conformal.
    xc=[]; yc=[]
    for axis,coords,controls in (('x',xs,xc),('y',ys,yc)):
        for i in range(len(coords)-1):
            middle=(coords[i]+coords[i+1])/2
            candidates=[r for r in p.regions if r[axis]<=middle<=r[axis]+r['width' if axis=='x' else 'height']]
            size=min([p.cell_size]+[r['size'] for r in candidates]); graded=[r for r in candidates if r['direction'].startswith(axis)]
            ratio=(graded[0]['ratio'] if graded[0]['direction'].endswith('+') else 1/graded[0]['ratio']) if graded else 1
            controls.append((max(1,math.ceil((coords[i+1]-coords[i])/size)),ratio))
    vid=lambda x,y,z:z*nx*ny+y*nx+x
    vertices=[(x,y,z) for z in (0,p.depth) for y in ys for x in xs]
    blocks=[]; patches={k:[] for k in ('inlet','outlet','farfield','front','back')}
    for iy in range(ny-1):
        for ix in range(nx-1):
            cx=(xs[ix]+xs[ix+1])/2; cy=(ys[iy]+ys[iy+1])/2
            r=next((r for r in p.regions if r['x']<=cx<=r['x']+r['width'] and r['y']<=cy<=r['y']+r['height']),None)
            size=r['size'] if r else p.cell_size; gx=gy=1
            if r and r['direction']!='uniform':
                ratio=r['ratio'] if r['direction'].endswith('+') else 1/r['ratio']
                if r['direction'].startswith('x'): gx=ratio
                else: gy=ratio
            v=[vid(ix,iy,0),vid(ix+1,iy,0),vid(ix+1,iy+1,0),vid(ix,iy+1,0),vid(ix,iy,1),vid(ix+1,iy,1),vid(ix+1,iy+1,1),vid(ix,iy+1,1)]
            blocks.append('hex ('+' '.join(map(str,v))+f') ({xc[ix][0]} {yc[iy][0]} {nz}) simpleGrading ({xc[ix][1]} {yc[iy][1]} 1)')
            if ix==0: patches['inlet'].append([v[k] for k in (0,4,7,3)])
            if ix==nx-2: patches['outlet'].append([v[k] for k in (1,2,6,5)])
            if iy==0: patches['farfield'].append([v[k] for k in (0,1,5,4)])
            if iy==ny-2: patches['farfield'].append([v[k] for k in (3,7,6,2)])
            patches['front'].append([v[k] for k in (0,3,2,1)]); patches['back'].append([v[k] for k in (4,5,6,7)])
    text=header('blockMeshDict')+'convertToMeters 1;\nvertices (\n'+''.join(f'({x} {y} {z})\n' for x,y,z in vertices)+');\nblocks (\n'+'\n'.join(blocks)+'\n);\nedges ();\nboundary (\n'
    for name,faces in patches.items():
        typ=('empty' if p.dimension==2 else 'symmetryPlane') if name in ('front','back') else 'patch'
        text+=name+' { type '+typ+'; faces ('+' '.join('('+' '.join(map(str,f))+')' for f in faces)+'); }\n'
    return text+');\nmergePatchPairs ();\n'
