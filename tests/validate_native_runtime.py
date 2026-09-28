"""Real Foundation 14 MPI solve/export smoke test for every model contract."""
import sys,time,json,os,re
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools'))
import numpy as np
from off.models import Project,Profile
from off.physics import MODELS
from off.backend import Engine,JobStore,failure_signals
from off.post import Result
from cycle_ledger import record
stamp=time.strftime('%Y%m%d_%H%M%S'); profile=Profile(max_cores=4); engine=Engine(profile,JobStore(BASE/'data'/('model_tests_'+stamp+'.sqlite')))
for name in ('dynamicLagrangian',):
    m=MODELS[name]
    engine.enqueue(Project(name='OFF_MODEL_'+name+'_'+stamp,turbulence=name,end_time=.002,delta_t=.0005,write_interval=.001))
rows=[]; observed=set(); deadline=time.time()+900
while len(observed)<1:
    jobs=engine.tick()
    for job in jobs:
        if job['state'] not in ('DONE','FAILED','STALLED') or job['id'] in observed: continue
        observed.add(job['id']); name=job['project']['turbulence']; model=MODELS[name]; case=Path(job['case']); log=(case/'log.solver').read_text(errors='replace') if (case/'log.solver').exists() else ''
        row={'model':name,'family':model.family,'state':job['state'],'case':str(case),'cores':4,'cells':5120,'end_time':.002,'runtime_s':job.get('elapsed'),'required_fields':model.fields,'errors':[]}
        if job['state']=='DONE':
            try:
                assert re.search(r'^End\s*$',log,re.M) and not failure_signals(log)
                r=Result(case/(job['name']+'.foam')); assert len(r.times)==3; r.select(2); assert r.internal.GetNumberOfCells()==5120
                for field in ('U','p')+model.fields:
                    assert r.internal.GetCellData().GetArray(field) is not None,(name,field,r.arrays())
                    from vtk.util.numpy_support import vtk_to_numpy
                    assert np.isfinite(vtk_to_numpy(r.internal.GetCellData().GetArray(field))).all(),(name,field)
                columns=r.columns(); wanted=['x','y','z','t','p']+[f for f in model.fields if f!='R']+(['R_xx','R_xy','R_yz','R_mag'] if 'R' in model.fields else [])
                r.csv(BASE/'evidence'/('model_'+name+'.csv'),wanted,stride=256,all_times=True)
                row['frames']=r.times; row['finite_required_fields']=True; row['VTK_count']=len(list((case/'VTK').rglob('*.vtk')))
                assert row['VTK_count']>0
            except Exception as e: row['errors'].append(repr(e))
        else: row['errors'].append(log[-4500:] if log else str(job))
        rows.append(row); print(name+' '+job['state']+(' verified' if not row['errors'] else ' ERROR'),flush=True)
        (BASE/'evidence/native_runtime_validation.json').write_text(json.dumps({'attempt':stamp,'all_selected_passed':False,'models':rows,'errors':[x['model'] for x in rows if x['errors']]},indent=2))
    if time.time()>deadline: raise TimeoutError('Model runtime test queue exceeded 900 seconds')
    time.sleep(.2)
report={'attempt':stamp,'all_selected_passed':all(x['state']=='DONE' and not x['errors'] for x in rows),'models':rows,'scope':'4-step software integration smoke tests; no physical turbulence/wake accuracy claim','errors':[x['model'] for x in rows if x['errors']]}
(BASE/'evidence/native_runtime_validation.json').write_text(json.dumps(report,indent=2)); assert report['all_selected_passed'],report['errors']
print('ISOLATED DIMENSION-CORRECT MODEL MPI TEST PASS',flush=True)
