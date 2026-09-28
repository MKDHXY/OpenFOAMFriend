"""Actual non-circular Gmsh 3D geometry -> four-rank solve -> real exports."""
import sys,os,time,json
from pathlib import Path
import numpy as np
from scipy.io import loadmat
from vtk.util.numpy_support import vtk_to_numpy
BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); os.environ['OFF_LANGUAGE']='en'
from PySide6.QtWidgets import QApplication
from off.backend import Engine,quality
from off.models import Profile
from off.templates import make_template
from off.post import Result
from off.viewer import Viewer
app=QApplication([]); engine=Engine(Profile(max_cores=4)); p=make_template('polygon'); p.name='OFF_POLYGON_FLOW_'+time.strftime('%Y%m%d_%H%M%S'); p.dimension=3; p.spanwise=4; p.cores=4; p.end_time=.05; p.delta_t=.0025; p.write_interval=.025
j=engine.enqueue(p); until=time.time()+180
while True:
    j=next(x for x in engine.tick() if x['id']==j['id'])
    assert j['state'] not in ('FAILED','STALLED','CANCELLED'),j
    if j['state']=='DONE': break
    assert time.time()<until,'Polygon pipeline timeout'
    app.processEvents(); time.sleep(.1)
case=Path(j['case']); q=quality(case); assert q['passed'] and q['skewness']<=.5 and q['non_orthogonality']<=30
r=Result(case/(p.name+'.foam')); assert r.internal.GetNumberOfCells()==6600 and np.allclose(r.times,[0,.025,.05])
for i in range(3):
    r.select(i)
    for field in ('U','p'): assert np.isfinite(vtk_to_numpy(r.internal.GetCellData().GetArray(field))).all()
out=BASE/'evidence/polygon_pipeline'; out.mkdir(exist_ok=True); r.csv(out/'fields.csv',['x','y','z','t','U_x','U_y','U_z','p'],stride=8,all_times=True); r.mat(out/'PINN.mat'); assert loadmat(out/'PINN.mat')['xytuvp'].shape==(3*6600,6)
v=Viewer(); v.resize(900,650); v.set_result(r); v.field.setCurrentIndex(v.field.findData('p')); v.show(); app.processEvents(); v.fit(); v.image().save(out/'pressure.png'); v.gif(str(out/'pressure.gif')); v.field.setCurrentIndex(v.field.findData('Mesh')); v.image().save(out/'mesh.png'); v.renderer.RemoveAllViewProps(); v.widget.Finalize(); v.close()
report={'release':BASE.name,'backend':'Gmsh -> gmshToFoam','actual_geometry':'pentagonal extruded obstacle','case':str(case),'cells':6600,'cores':4,'end_time_s':.05,'genuine_frames':3,'quality':q,'max_observed_Co':j['max_observed_co'],'CSV_MAT_PNG_GIF':True,'errors':[]}
(BASE/'evidence/polygon_pipeline_validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
