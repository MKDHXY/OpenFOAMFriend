"""SI geometry context for planar manual topology; references never mesh silently."""
import math
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QColor,QPen,QBrush,QPainterPath,QPolygonF
from PySide6.QtWidgets import QGraphicsItem
from .geometry import vertices
from .i18n import text
from . import manual_topology as topo

def points(project):
    p=project; out=[(p.xmin,p.ymin),(p.xmax,p.ymin),(p.xmax,p.ymax),(p.xmin,p.ymax)]
    for s in p.shapes:
        if s['kind']=='circle':out.extend((s['x']+s['width']/2*math.cos(i*math.pi/2),s['y']+s['height']/2*math.sin(i*math.pi/2)) for i in range(4))
        else:out.extend(vertices(s))
    return out

def paint(scene,p,scale=1):
    """Dashed outlines stay above region fills, below editable topology edges."""
    def outline(path,label,colour,xy,fill=None,visible=True):
        pen=QPen(QColor(colour),1.5,Qt.DashLine);pen.setCosmetic(True)
        item=scene.addPath(path,pen,QBrush(QColor(fill)) if fill else QBrush(Qt.NoBrush));item.setZValue(.5);item.setData(1,'reference');item.setAcceptedMouseButtons(Qt.NoButton)
        lab=scene.addSimpleText(label);lab.setBrush(QColor(colour));lab.setFlag(QGraphicsItem.ItemIgnoresTransformations);lab.setPos(xy[0],-xy[1]);lab.setZValue(1);lab.setData(1,'reference');lab.setAcceptedMouseButtons(Qt.NoButton);lab.setVisible(visible)
    path=QPainterPath();path.addRect(p.xmin,-p.ymax,p.xmax-p.xmin,p.ymax-p.ymin)
    outline(path,text('Design extent','设计流场范围')+f' · {p.xmax-p.xmin:g} × {p.ymax-p.ymin:g} m','#718c9e',(p.xmin,p.ymax))
    if p.mesh_method=='Structured cylinder O-grid' and len(p.shapes)==1:
        s=p.shapes[0];r=p.outer_radius;path=QPainterPath();path.addEllipse(QPointF(s['x'],-s['y']),r,r)
        outline(path,text('O-grid outer radius','O-grid 外半径')+f' = {r:g} m','#947043',(s['x']-r,s['y']+r))
    for s in p.shapes:
        path=QPainterPath()
        if s['kind']=='circle':path.addEllipse(QPointF(s['x'],-s['y']),s['width']/2,s['height']/2)
        else:path.addPolygon(QPolygonF([QPointF(x,-y) for x,y in vertices(s)]));path.closeSubpath()
        outline(path,s.get('name','solid')+f' · {s["width"]:g} × {s["height"]:g} m','#505c68',(s['x']-s['width']/2,s['y']+s['height']/2+24/max(scale,1e-10)),visible=s['width']*scale>55)
    for r in p.regions:
        path=QPainterPath();path.addRect(r['x'],-r['y']-r['height'],r['width'],r['height'])
        outline(path,text('Refinement reference','加密区参考')+f' · h={r["size"]:g} m','#9b7daf',(r['x'],r['y']+r['height']))

def import_boundaries(g,p):
    """Explicitly add domain/solid loops. Existing graph is retained; one undo transaction."""
    def polygon_loop(pts,patches):
        ns=[topo.add_node(g,v) for v in pts]
        for i in range(len(ns)):
            a,b=ns[i],ns[(i+1)%len(ns)]
            existing=next((e for e in g['edges'] if {e['a'],e['b']}=={a,b}),None)
            if existing:
                if existing['kind']!='line':raise ValueError('Existing arc conflicts with a straight reference boundary / 已有圆弧与直线参考边界冲突')
            else:topo.add_edge(g,a,b,patch=patches[i])
    polygon_loop([(p.xmin,p.ymin),(p.xmax,p.ymin),(p.xmax,p.ymax),(p.xmin,p.ymax)],['farfield','outlet','farfield','inlet'])
    for s in p.shapes:
        if s['kind']=='circle':
            if abs(s['width']-s['height'])>1e-10:raise ValueError('Ellipse import needs an explicit curve representation / 椭圆导入需要明确曲线表示')
            x,y=s['x'],s['y'];r=s['width']/2;ns=[topo.add_node(g,(x+r*math.cos(i*math.pi/2),y+r*math.sin(i*math.pi/2))) for i in range(4)]
            for i in range(4):
                a,b=ns[i],ns[(i+1)%4];through=(x+r*math.cos((i+.5)*math.pi/2),y+r*math.sin((i+.5)*math.pi/2))
                e=next((e for e in g['edges'] if {e['a'],e['b']}=={a,b}),None)
                if e:
                    if e['kind']!='arc' or math.dist(topo.point(g,e,.5),through)>1e-9:raise ValueError('Existing curve conflicts with reference arc / 已有曲线与参考圆弧冲突')
                else:topo.add_edge(g,a,b,through,count=16,patch='cylinder')
        else:polygon_loop(vertices(s),['cylinder']*len(vertices(s)))
    # A closed solid reference must be an actual hole, never a fluid mesh region.
    for f in topo.faces(g):
        solid=False
        for s in p.shapes:
            if s['kind']=='circle':
                solid=all(abs(math.hypot(x-s['x'],y-s['y'])-s['width']/2)<1e-7*max(s['width'],1e-6) for x,y in f['poly'])
            else:
                vv=vertices(s);solid=all(any(math.dist(v,q)<1e-9 for q in vv) for v in f['poly']) and len(f['poly'])==len(vv)
            if solid:break
        if solid:g['regions'][f['key']]={**topo.defaults(),'role':'hole'}
        elif f['key'] not in g['regions']:g['regions'][f['key']]={**topo.defaults(),'method':'tri','size':p.cell_size}

def cylinder_blocks(p):
    if len(p.shapes)!=1 or p.shapes[0]['kind']!='circle':raise ValueError('Cylinder blocks require one circular model / 圆柱分块需要单个圆形模型')
    s=p.shapes[0];radius=s['width']/2
    if abs(s['width']-s['height'])>1e-10 or p.outer_radius<=radius:raise ValueError('Circular model and larger outer radius required / 需要圆形模型及更大的外半径')
    g=topo.cylinder_preset(); x,y=s['x'],s['y']
    for k,v in g['nodes'].items():
        factor=radius/.5 if math.hypot(*v)<1 else p.outer_radius/10;g['nodes'][k]=[x+v[0]*factor,y+v[1]*factor]
    for e in g['edges']:
        if e['kind']=='arc':
            v=e['through'];factor=radius/.5 if e['patch']=='cylinder' else p.outer_radius/10;e['through']=[x+v[0]*factor,y+v[1]*factor];e['count']=p.circumferential//4
        else:e['count']=p.radial;e['ratio']=p.grading
    # Face keys use signed edge IDs and remain unchanged by SI scaling.
    return g
