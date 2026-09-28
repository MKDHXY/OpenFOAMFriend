"""Dimensioned starter geometries with explicit boundary/accuracy scope."""
import time,copy
from .models import Project
from .geometry import polygon
from .i18n import text

def examples():
    names=[('cylinder3d','3D circular cylinder / O-grid','三维圆柱 / O-grid'),('cylinder2d','2D circular cylinder / O-grid','二维圆柱 / O-grid'),('square','Square bluff body','方柱钝体'),('triangle','Triangular bluff body','三角形钝体'),('tandem','Two tandem cylinders','串列双圆柱'),('polygon','Custom polygon bluff body','自定义多边形钝体'),('box','Uniform rectangular flow / manual blocks','均匀矩形流场 / 手动分块')]
    return [(key,text(en,zh)) for key,en,zh in names]

def make_template(key):
    p=Project(name='Starter_'+key+'_'+time.strftime('%Y%m%d_%H%M%S'),end_time=10,delta_t=.005,write_interval=.5)
    if key=='cylinder3d': pass
    elif key=='cylinder2d': p.dimension=2; p.spanwise=1
    elif key=='box': p.shapes=[]; p.reference_length=1; p.xmin=-2; p.xmax=6; p.ymin=-2; p.ymax=2; p.cell_size=.25; p.mesh_method='Structured partitioned box'
    else:
        p.mesh_method='Gmsh triangle / prism'; p.cell_size=.5; p.xmin=-5; p.xmax=10; p.ymin=-5; p.ymax=5; p.reference_length=1
        if key=='tandem':
            p.shapes=[{'kind':'circle','name':'cylinder1','x':0.,'y':0.,'width':1.,'height':1.},{'kind':'circle','name':'cylinder2','x':3.,'y':0.,'width':1.,'height':1.}]
        elif key=='polygon': p.shapes=[polygon([[-.6,-.4],[.2,-.5],[.7,0],[.2,.5],[-.6,.4]],'pentagon')]; p.dimension=2; p.spanwise=1
        elif key in ('square','triangle'): p.shapes=[{'kind':'rectangle' if key=='square' else 'triangle','name':key,'x':0.,'y':0.,'width':1.,'height':1.}]; p.dimension=2; p.spanwise=1
        else: raise ValueError('Unknown starter case.')
    p.validate(); return p
