"""SI planar boundary graph, face extraction, editing and genuine mesh compilers."""
import math,copy,json
from collections import Counter

METHODS=('Manual topology (blockMesh)','Manual topology (Gmsh)')

def empty(): return {'nodes':{},'edges':[],'regions':{}}
def node(g,i): return g['nodes'][str(i)]
def edge(g,i): return next(e for e in g['edges'] if e['id']==abs(i))
def add_node(g,xy,tol=1e-9):
    for k,v in g['nodes'].items():
        if math.dist(v,xy)<tol:return int(k)
    i=max(map(int,g['nodes']),default=0)+1; g['nodes'][str(i)]=list(map(float,xy)); return i
def add_edge(g,a,b,through=None,count=8,ratio=1,patch='auto'):
    if a==b:raise ValueError('A curve requires distinct endpoints / 曲线两端不能重合。')
    if any({e['a'],e['b']}=={a,b} and e['kind']==('arc' if through else 'line') for e in g['edges']):raise ValueError('Duplicate edge / 重复边。')
    i=max([e['id'] for e in g['edges']],default=0)+1
    e=dict(id=i,a=a,b=b,kind='arc' if through else 'line',count=int(count),ratio=float(ratio),patch=patch)
    if through:e['through']=list(through); arc_geometry(g,e)
    g['edges'].append(e); return i
def arc_geometry(g,e):
    (ax,ay),(bx,by)=node(g,e['a']),node(g,e['b']); mx,my=e['through']
    det=2*(ax*(by-my)+bx*(my-ay)+mx*(ay-by))
    scale=max(math.dist((ax,ay),(bx,by)),math.dist((ax,ay),(mx,my)))
    if abs(det)<1e-10*scale*scale:raise ValueError('Three arc points are collinear / 圆弧三点共线。')
    aa=ax*ax+ay*ay; bb=bx*bx+by*by; mm=mx*mx+my*my
    cx=(aa*(by-my)+bb*(my-ay)+mm*(ay-by))/det; cy=(aa*(mx-bx)+bb*(ax-mx)+mm*(bx-ax))/det
    start=math.atan2(ay-cy,ax-cx); end=math.atan2(by-cy,bx-cx); mid=math.atan2(my-cy,mx-cx)
    sweep=(end-start)%(2*math.pi)
    if (mid-start)%(2*math.pi)>sweep:sweep-=2*math.pi
    return cx,cy,math.hypot(ax-cx,ay-cy),start,sweep
def point(g,e,t):
    if e['kind']=='line':return tuple((1-t)*x+t*y for x,y in zip(node(g,e['a']),node(g,e['b'])))
    x,y,r,a,s=arc_geometry(g,e); return x+r*math.cos(a+t*s),y+r*math.sin(a+t*s)
def samples(g,e,n=48):return [point(g,e,i/n) for i in range(n+1)] if e['kind']=='arc' else [node(g,e['a']),node(g,e['b'])]
def projection(g,e,xy):
    a,b=node(g,e['a']),node(g,e['b'])
    if e['kind']=='line':
        t=max(0,min(1,sum((xy[i]-a[i])*(b[i]-a[i]) for i in (0,1))/sum((b[i]-a[i])**2 for i in (0,1))))
    else:
        x,y,r,start,sweep=arc_geometry(g,e); angle=math.atan2(xy[1]-y,xy[0]-x)
        raw=((angle-start)%(2*math.pi)) if sweep>0 else -((start-angle)%(2*math.pi)); t=raw/sweep
        if not 0<=t<=1:t=0 if math.dist(xy,a)<math.dist(xy,b) else 1
    q=point(g,e,t);return t,q,math.dist(q,xy)
def split(g,eid,xy):
    e=edge(g,eid); t,q,_=projection(g,e,xy)
    if not 1e-6<t<1-1e-6:raise ValueError('Split inside the edge, not at an endpoint / 请在边内部打断。')
    before=faces(g); saved=copy.deepcopy(g['regions']); k=add_node(g,q); n=max(2,e['count']); n1=max(1,min(n-1,round(n*t))); n2=n-n1; prog=e['ratio']**(1/max(1,n-1))
    # Allocate fresh IDs before removal so region identities never silently reuse an erased edge.
    i=add_edge(g,e['a'],k,point(g,e,t/2) if e['kind']=='arc' else None,n1,prog**max(0,n1-1),e['patch'])
    j=add_edge(g,k,e['b'],point(g,e,(1+t)/2) if e['kind']=='arc' else None,n2,prog**max(0,n2-1),e['patch'])
    g['edges'].remove(e); remap_regions(g,before,saved);return k,(i,j)
def erase(g,eid):
    g['edges']=[e for e in g['edges'] if e['id']!=abs(eid)]
    used={e[k] for e in g['edges'] for k in ('a','b')}; g['nodes']={k:v for k,v in g['nodes'].items() if int(k) in used}
    existing={f['key'] for f in faces(g)}; g['regions']={k:v for k,v in g['regions'].items() if k in existing}
def area(poly):return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1]))/2
def inside(xy,poly):
    x,y=xy; hit=False
    for a,b in zip(poly,poly[1:]+poly[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:hit=not hit
    return hit
def faces(g):
    """CCW bounded half-edge walks. Shared boundary curves are single graph objects."""
    adj={int(k):[] for k in g['nodes']}
    for e in g['edges']:
        for sign,u in [(1,e['a']),(-1,e['b'])]:
            p=node(g,u); q=point(g,e,.001 if sign==1 else .999); adj[u].append((math.atan2(q[1]-p[1],q[0]-p[0]),sign*e['id']))
    for v in adj.values():v.sort()
    visited=set(); result=[]
    for e in g['edges']:
        for start in (e['id'],-e['id']):
            if start in visited:continue
            walk=[]; vertices=[]; poly=[]; current=start
            while current not in visited:
                visited.add(current); walk.append(current); ce=edge(g,current); a,b=(ce['a'],ce['b']) if current>0 else (ce['b'],ce['a']); vertices.append(a)
                pts=samples(g,ce); poly.extend((pts if current>0 else pts[::-1])[:-1]); opts=[x[1] for x in adj[b]]; current=opts[(opts.index(-current)-1)%len(opts)]
            ar=area(poly)
            if current==start and ar>1e-12 and len(walk)>=3:
                result.append(dict(key='F_'+ '_'.join(map(str,sorted(abs(i) for i in walk))),edges=walk,vertices=vertices,poly=poly,area=ar))
    return sorted(result,key=lambda f:f['key'])
def defaults():return dict(role='fluid',method='mapped',size=.5,name='fluid_region')
def settings(g,f):return {**defaults(),**g['regions'].get(f['key'],{})}
def remap_regions(g,previous,saved):
    for f in faces(g):
        xy=tuple(sum(v[i] for v in f['poly'])/len(f['poly']) for i in (0,1))
        old=next((r for r in previous if inside(xy,r['poly']) and r['key'] in saved),None)
        if old:g['regions'][f['key']]=copy.deepcopy(saved[old['key']])
def children(allfaces,f):
    small=[s for s in allfaces if s['area']<f['area'] and not set(map(abs,s['edges']))&set(map(abs,f['edges'])) and inside(s['poly'][0],f['poly'])]
    return [s for s in small if not any(o['area']>s['area'] and inside(s['poly'][0],o['poly']) for o in small)]
def validate(g,backend='Gmsh'):
    if not g.get('nodes') or not g.get('edges'):raise ValueError('Draw a closed region first / 请先绘制闭合区域。')
    if len({e['id'] for e in g['edges']})!=len(g['edges']):raise ValueError('Duplicate curve IDs')
    for n in g['nodes'].values():
        if len(n)!=2 or not all(math.isfinite(v) for v in n):raise ValueError('Invalid node coordinates')
    for e in g['edges']:
        if e['a']==e['b'] or str(e['a']) not in g['nodes'] or str(e['b']) not in g['nodes']:raise ValueError('Invalid edge endpoints')
        if not isinstance(e['count'],int) or e['count']<1 or not math.isfinite(e['ratio']) or e['ratio']<=0:raise ValueError('Curve cells >=1 and spacing ratio >0 required')
        if e['kind']=='arc':arc_geometry(g,e)
    # Crossing interior edges require an explicit common node. Approximate arc intersection
    # detection screens geometry; actual generator/checkMesh is the final mesh gate.
    def segments_intersect(a,b,c,d):
        def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return True
        def onseg(v,x,y):return abs(cross(x,y,v))<1e-12 and min(x[0],y[0])-1e-10<=v[0]<=max(x[0],y[0])+1e-10 and min(x[1],y[1])-1e-10<=v[1]<=max(x[1],y[1])+1e-10
        return onseg(a,c,d) or onseg(b,c,d) or onseg(c,a,b) or onseg(d,a,b)
    for i,e in enumerate(g['edges']):
        ep=samples(g,e)
        for other in g['edges'][i+1:]:
            op=samples(g,other); shared={e['a'],e['b']}&{other['a'],other['b']}
            for j,(a,b) in enumerate(zip(ep,ep[1:])):
                for k,(c,d) in enumerate(zip(op,op[1:])):
                    if shared and any(math.dist(v,node(g,n))<1e-8 for n in shared for v in (a,b)) and any(math.dist(v,node(g,n))<1e-8 for n in shared for v in (c,d)):continue
                    if segments_intersect(a,b,c,d):raise ValueError(f'Curves E{e["id"]}, E{other["id"]} cross without a node / 交叉处须打断并共用节点。')
    fs=faces(g); used={abs(i) for f in fs for i in f['edges']}
    if not fs or any(e['id'] not in used for e in g['edges']) or any(len(set(map(abs,f['edges'])))!=len(f['edges']) for f in fs):raise ValueError('Open/dangling topology. Close regions or erase dangling segments / 存在开口或悬边，请闭合或擦除。')
    fluid=[f for f in fs if settings(g,f)['role']=='fluid']
    if not fluid:raise ValueError('No fluid region / 没有流体区域。')
    for f in fluid:
        s=settings(g,f)
        if s['method']=='mapped' or backend=='blockMesh':
            if len(f['edges'])!=4 or children(fs,f):raise ValueError(f'{f["key"]}: mapped/blockMesh needs four edges and no holes. Choose Tri/Quad for split-sided polygons / 映射区域要求四边且无孔，拆边多边形请选择三角/四边形主导。')
            ee=[edge(g,i) for i in f['edges']]
            if ee[0]['count']!=ee[2]['count'] or ee[1]['count']!=ee[3]['count']:raise ValueError('Opposite mapped edges need equal cell counts; use Assign region / 对边单元数不一致，请用区域指派。')
            if backend=='blockMesh':
                rr=[e['ratio'] if i>0 else 1/e['ratio'] for e,i in zip(ee,f['edges'])]
                if not math.isclose(rr[0]*rr[2],1,rel_tol=1e-8) or not math.isclose(rr[1]*rr[3],1,rel_tol=1e-8):raise ValueError('blockMesh opposite-edge distributions differ; reassign regional ratios / blockMesh 对边分布不一致，请重新指派区域间距比。')
        if s['size']<=0:raise ValueError('Region target size must be positive')
    return fs,fluid
def assign(g,key,nx,ny,gx=1,gy=1,**opts):
    f=next(f for f in faces(g) if f['key']==key); s={**settings(g,f),**opts}; g['regions'][key]=s
    if s['method']!='mapped' or s['role']=='hole':return
    if len(f['edges'])!=4:raise ValueError('Mapped assignment needs a four-edge region / 映射指派需要四边区域。')
    # Equality constraints propagate through all mapped neighbours: no duplicated interface grids.
    fs=[f for f in faces(g) if settings(g,f)['role']=='fluid' and settings(g,f)['method']=='mapped' and len(f['edges'])==4]
    parent={e['id']:e['id'] for e in g['edges']}
    def find(x):
        while parent[x]!=x:x=parent[x]
        return x
    for r in fs:
        for a,b in ((0,2),(1,3)):parent[find(abs(r['edges'][a]))]=find(abs(r['edges'][b]))
    wanted={}
    for pos,count in [(0,nx),(1,ny)]:
        root=find(abs(f['edges'][pos]))
        if root in wanted and wanted[root]!=count:raise ValueError('Connected topology forces Nx=Ny here / 连通约束要求此处 Nx=Ny。')
        wanted[root]=int(count)
    for e in g['edges']:
        if find(e['id']) in wanted:e['count']=wanted[find(e['id'])]
    # Signed log-ratios enforce identical node spacing on opposite curves.
    # A shared curve is one entity: edits propagate through its mapped neighbours.
    links={e['id']:[] for e in g['edges']}
    for r in fs:
        for a,b in ((0,2),(1,3)):
            i,j=r['edges'][a],r['edges'][b]; factor=-1 if i*j>0 else 1
            links[abs(i)].append((abs(j),factor));links[abs(j)].append((abs(i),factor))
    values={}
    for i,ratio in zip(f['edges'],(gx,gy,1/gx,1/gy)):
        if ratio<=0 or not math.isfinite(ratio):raise ValueError('Spacing ratio must be finite and positive')
        pending=[(abs(i),math.log(ratio)*(1 if i>0 else -1))]
        while pending:
            n,value=pending.pop()
            if n in values:
                if not math.isclose(values[n],value,abs_tol=1e-9):raise ValueError('Connected mapped regions require compatible spacing ratios / 连通映射区域要求兼容的间距比。')
                continue
            values[n]=value;pending.extend((other,value*factor) for other,factor in links[n])
    for n,value in values.items():edge(g,n)['ratio']=math.exp(value)
def patch_name(g,e):
    if e['patch']!='auto':return e['patch']
    xs=[v[0] for v in g['nodes'].values()]; a,b=node(g,e['a']),node(g,e['b']); eps=max(max(xs)-min(xs),1)*1e-8
    if e['kind']=='line' and abs(a[0]-min(xs))<eps and abs(b[0]-min(xs))<eps:return 'inlet'
    if e['kind']=='line' and abs(a[0]-max(xs))<eps and abs(b[0]-max(xs))<eps:return 'outlet'
    return 'farfield'
def block_dict(p):
    from .mesh import header
    g=p.manual_mesh; fs,fluid=validate(g,'blockMesh'); ids=sorted(map(int,g['nodes'])); ix={n:i for i,n in enumerate(ids)}; nn=len(ids); nz=p.spanwise if p.dimension==3 else 1
    pts=[(*node(g,n),z) for z in (0,p.depth) for n in ids]; blocks=[]; arcs=[]; patches={k:[] for k in ('inlet','outlet','farfield','cylinder','front','back')}; used=Counter(abs(i) for f in fluid for i in f['edges'])
    for f in fluid:
        v=[ix[n] for n in f['vertices']]; ee=[edge(g,i) for i in f['edges']]; rr=[e['ratio'] if i>0 else 1/e['ratio'] for e,i in zip(ee,f['edges'])]
        blocks.append('hex ('+' '.join(map(str,v+[n+nn for n in v]))+f') ({ee[0]["count"]} {ee[1]["count"]} {nz}) simpleGrading ({rr[0]:.12g} {1/rr[3]:.12g} 1)')
        patches['front'].append(v[::-1]); patches['back'].append([n+nn for n in v])
        for k,i in enumerate(f['edges']):
            if used[abs(i)]==1:
                name=patch_name(g,edge(g,i))
                if name not in patches or name in ('front','back'):raise ValueError('Assign inlet/outlet/farfield/cylinder on external curves')
                a,b=v[k],v[(k+1)%4]; patches[name].append([a,b,b+nn,a+nn])
    for e in g['edges']:
        if e['kind']=='arc':
            for z,offset in [(0,0),(p.depth,nn)]:arcs.append(f'arc {ix[e["a"]]+offset} {ix[e["b"]]+offset} ({e["through"][0]:.12g} {e["through"][1]:.12g} {z:.12g})')
    text=header('blockMeshDict')+'convertToMeters 1;\nvertices (\n'+''.join('('+ ' '.join(f'{x:.12g}' for x in q)+')\n' for q in pts)+');\nblocks (\n'+'\n'.join(blocks)+');\nedges (\n'+'\n'.join(arcs)+');\nboundary (\n'
    for name,polys in patches.items():
        typ='wall' if name=='cylinder' else ('empty' if p.dimension==2 else 'symmetryPlane') if name in ('front','back') else 'patch'
        text+=name+' { type '+typ+'; faces ('+' '.join('('+' '.join(map(str,f))+')' for f in polys)+'); }\n'
    return text+');\nmergePatchPairs ();\n'
def build_gmsh(p,path):
    import gmsh
    g=p.manual_mesh; fs,fluid=validate(g); gmsh.initialize(interruptible=False); gmsh.option.setNumber('General.Terminal',0)
    try:
        gmsh.model.add(p.name); geo=gmsh.model.geo
        nmap={int(n):geo.addPoint(*v,0,p.cell_size) for n,v in g['nodes'].items()}; emap={}
        for e in g['edges']:
            if e['kind']=='line':emap[e['id']]=geo.addLine(nmap[e['a']],nmap[e['b']])
            else:
                x,y,r,a,s=arc_geometry(g,e)
                if abs(s)>=math.pi-1e-8:raise ValueError('For Gmsh, split arcs at 180 degrees or larger / Gmsh 请将 >=180° 圆弧打断。')
                center=geo.addPoint(x,y,0); emap[e['id']]=geo.addCircleArc(nmap[e['a']],center,nmap[e['b']])
        loops={f['key']:geo.addCurveLoop([emap[abs(i)]*(1 if i>0 else -1) for i in f['edges']]) for f in fs}
        surfaces={f['key']:geo.addPlaneSurface([loops[f['key']]]+[loops[s['key']] for s in children(fs,f)]) for f in fluid}
        # Protect sharp corners of triangular surfaces. An embedded interior seed
        # prevents a corner cell from having only one internal neighbour face.
        seeds={}
        for f in fluid:
            if settings(g,f)['method']!='tri':continue
            tags=[]; v=f['vertices']
            for k,n in enumerate(v):
                xy=node(g,n); prev=node(g,v[k-1]); nxt=node(g,v[(k+1)%len(v)])
                l1=math.dist(xy,prev); l2=math.dist(xy,nxt); a=[(prev[i]-xy[i])/l1 for i in (0,1)]; b=[(nxt[i]-xy[i])/l2 for i in (0,1)]
                if sum(a[i]*b[i] for i in (0,1))<-.9:continue
                direction=[a[i]+b[i] for i in (0,1)]; norm=math.hypot(*direction)
                if norm<1e-8:continue
                distance=.4*min(l1/edge(g,f['edges'][k-1])['count'],l2/edge(g,f['edges'][k])['count'],settings(g,f)['size'])
                seed=[xy[i]+distance*direction[i]/norm for i in (0,1)]
                if inside(seed,f['poly']) and not any(inside(seed,c['poly']) for c in children(fs,f)):tags.append(geo.addPoint(*seed,0,distance))
            seeds[surfaces[f['key']]]=tags
        geo.synchronize()
        for e in g['edges']:geo.mesh.setTransfiniteCurve(emap[e['id']],e['count']+1,'Progression',e['ratio']**(1/max(1,e['count']-1)))
        for f in fluid:
            s=settings(g,f); tag=surfaces[f['key']]
            geo.mesh.setSize([(0,nmap[n]) for n in f['vertices']],s['size'])
            if s['method']=='mapped':geo.mesh.setTransfiniteSurface(tag,cornerTags=[nmap[n] for n in f['vertices']])
            if s['method'] in ('mapped','quad'):geo.mesh.setRecombine(2,tag)
        out=geo.extrude([(2,t) for t in surfaces.values()],0,0,p.depth,numElements=[p.spanwise if p.dimension==3 else 1],recombine=True); geo.synchronize()
        for surface,tags in seeds.items():
            if tags:gmsh.model.mesh.embed(0,tags,2,surface)
        vols=[t for dim,t in out if dim==3]; counts=Counter(t for vol in vols for dim,t in gmsh.model.getBoundary([(3,vol)],oriented=False) if dim==2)
        patches={k:[] for k in ('inlet','outlet','farfield','cylinder','front','back')}; base=set(surfaces.values()); reverse={v:k for k,v in emap.items()}
        for t,n in counts.items():
            if n!=1:continue
            b=gmsh.model.getBoundingBox(2,t)
            if t in base:name='front'
            elif abs(b[2]-p.depth)<1e-7 and abs(b[5]-p.depth)<1e-7:name='back'
            else:
                original=[c for dim,c in gmsh.model.getBoundary([(2,t)],oriented=False) if dim==1 and c in reverse]
                if len(original)!=1:raise ValueError('Cannot map extrusion boundary to sketch curve')
                name=patch_name(g,edge(g,reverse[original[0]]))
                if name not in patches:raise ValueError('External curve cannot be marked interior / 外边界不能标为内部。')
            patches[name].append(t)
        for name,tags in patches.items():
            if tags:gmsh.model.setPhysicalName(2,gmsh.model.addPhysicalGroup(2,tags),name)
        gmsh.model.setPhysicalName(3,gmsh.model.addPhysicalGroup(3,vols),'fluid'); gmsh.option.setNumber('Mesh.MshFileVersion',2.2); gmsh.option.setNumber('Mesh.Smoothing',p.smoothing)
        gmsh.write(str(path.with_suffix('.geo_unrolled'))); gmsh.model.mesh.generate(3); gmsh.write(str(path)); gmsh.write(str(path.with_suffix('.vtk')))
        return {'elements':sum(len(a) for a in gmsh.model.mesh.getElements(3)[1]),'mesh':str(path)}
    finally:gmsh.finalize()
def cylinder_preset():
    g=empty(); inner=[]; outer=[]
    for radius,nodes in [(.5,inner),(10,outer)]:
        for i in range(4):nodes.append(add_node(g,(radius*math.cos(i*math.pi/2),radius*math.sin(i*math.pi/2))))
    for i in range(4):
        mid=(i+.5)*math.pi/2; j=(i+1)%4
        add_edge(g,inner[i],inner[j],(.5*math.cos(mid),.5*math.sin(mid)),16,1,'cylinder')
        add_edge(g,outer[i],outer[j],(10*math.cos(mid),10*math.sin(mid)),16,1,'outlet' if i in (0,3) else 'inlet')
        add_edge(g,inner[i],outer[i],count=20)
    for f in faces(g):g['regions'][f['key']]={**defaults(),'role':'hole' if f['area']<1 else 'fluid'}
    return g
