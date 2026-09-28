"""A real additional 2D OpenFOAM solve and MAT export, not an interpolated 3D result."""
import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.io import loadmat
from off.models import Project,load_profile
from off.backend import Engine,BASE
from off.post import Result
from off.quality import audit
engine=Engine(load_profile()); p=Project(name='OFF_2D_'+time.strftime('%Y%m%d_%H%M%S'),dimension=2,spanwise=1,end_time=.02,delta_t=.0005,write_interval=.01); j=engine.enqueue(p); deadline=time.time()+240
while True:
    jobs=engine.tick(); j=next(x for x in jobs if x['id']==j['id'])
    if j['state'] in ('DONE','FAILED'): break
    if time.time()>deadline: raise TimeoutError(j)
    time.sleep(1)
assert j['state']=='DONE',j; case=Path(j['case']); result=Result(next(case.glob('*.foam'))); assert result.internal.GetNumberOfCells()==1280 and len(result.times)==3
out=BASE/'evidence'; result.mat(out/'twoD.mat'); data=loadmat(out/'twoD.mat'); assert np.isfinite(data['xyztuvwp']).all() and len(np.unique(data['xyztuvwp'][:,2]))==1
qa=audit(case)[0]; assert qa['nonpositive_cells']==0 and qa['max_skewness']<.5
report={'real_2D_solver':'DONE','cells':1280,'cores':4,'genuine_frames':len(result.times),'end_s':result.times[-1],'unique_z_layers':1,'finite_MAT':True,'quality':qa,'case':str(case),'errors':[]}
(out/'twoD_pipeline_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
