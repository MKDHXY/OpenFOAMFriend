"""Re endpoints and Re3900 are integration smoke checks, not accuracy claims."""
import sys,os,time,json,re
from pathlib import Path
import numpy as np
from vtk.util.numpy_support import vtk_to_numpy
BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from off.models import Project,Profile
from off.backend import Engine,JobStore
from off.post import Result
stamp=time.strftime('%Y%m%d_%H%M%S'); engine=Engine(Profile(max_cores=4),JobStore(BASE/'data'/('range_tests_'+stamp+'.sqlite')))
for target,model in ((1,'laminar'),(3900,'kOmegaSST'),(10000000,'kOmegaSST')):
    engine.enqueue(Project(name=f'OFF_RE_{target}_{stamp}',viscosity=1/target,turbulence=model,end_time=.002,delta_t=.0005,write_interval=.001))
deadline=time.time()+180
while True:
    jobs=engine.tick()
    if any(j['state'] in ('FAILED','STALLED') for j in jobs): raise AssertionError(json.dumps(jobs,indent=2))
    if all(j['state']=='DONE' for j in jobs): break
    if time.time()>deadline: raise TimeoutError('Range integration queue exceeded 180s')
    time.sleep(.2)
rows=[]
for j in jobs:
    p=j['project']; case=Path(j['case']); r=Result(case/(j['name']+'.foam')); assert r.internal.GetNumberOfCells()==5120 and len(r.times)==3
    r.select(2)
    for name in ('U','p'): assert np.isfinite(vtk_to_numpy(r.internal.GetCellData().GetArray(name))).all()
    log=(case/'log.solver').read_text(); co=[float(x) for x in re.findall(r'Courant Number mean:.*?max:\s*([\d.eE+-]+)',log)]; assert max(co)<=.3
    rows.append({'Re':p['velocity']/p['viscosity'],'model':p['turbulence'],'cells':5120,'cores':4,'case':str(case),'frames':r.times,'max_Co':max(co),'finite':True})
report={'release':BASE.name,'runs':rows,'errors':[],'scope':'Four-step software/parameter integration only. Coarse high-Re meshes and symmetry span boundaries do not validate turbulent wake physics.'}
(BASE/'evidence/re_range_runtime.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
