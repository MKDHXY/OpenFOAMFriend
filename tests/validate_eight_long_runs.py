"""Eight sequential genuine >=10s 5120-cell/4-core full-pipeline QA rounds.

The script stops on a defect rather than silently calling a failed round PASS.
An existing completed round can be reopened/rechecked when resuming the script.
"""
import sys,os,time,json,re,traceback
from pathlib import Path
import numpy as np
from scipy.io import loadmat
from vtk.util.numpy_support import vtk_to_numpy
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication
from off.models import Project,Profile
from off.backend import Engine,failure_signals,parse_log
from off.physics import MODELS
from off.post import Result
from off.viewer import Viewer
from off.quality import audit
app=QApplication([]); engine=Engine(Profile(max_cores=4)); out=BASE/'evidence/eight_long_runs'; out.mkdir(exist_ok=True)
status_file=out/'status.json'; ledger_file=out/'ledger.json'
if ledger_file.exists(): ledger=json.loads(ledger_file.read_text(encoding='utf-8'))
else: ledger={'release':BASE.name,'stamp':time.strftime('%Y%m%d_%H%M%S'),'rounds':[],'failures':[],'scope':'Software integration and finite-field stability screening. 10s / 5120 cells is not a DNS/LES accuracy or statistical convergence certificate.'}
stamp=ledger['stamp']; viewer=Viewer(); viewer.resize(950,650)
plan=[('laminar',200,.005,'Baseline 3D laminar pipeline'),('laminar',1,.005,'Diffusion-dominated Re1 endpoint'),('laminar',200,.0025,'Finer internal dt and real pause/continue'),('kOmegaSST',3900,.005,'URANS SST full model fields'),('kOmegaSST',10000000,.005,'High-Re parameter endpoint; no accuracy claim'),('WALE',3900,.005,'3D LES interface and algebraic SGS fields'),('kOmegaSSTDES',3900,.005,'Hybrid interface, delta and required fields'),('dynamicLagrangian',3900,.005,'Isolated native model over 10s, U^4 averaging fields')]
def persist(): ledger_file.write_text(json.dumps(ledger,indent=2),encoding='utf-8')
def status(stage,number,job=None,extra=None):
    row={'release':BASE.name,'stage':stage,'active_round':number,'completed_rounds':len(ledger['rounds']),'updated_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    if job: row.update({'case':job['name'],'state':job['state'],'time_s':job.get('time',0),'end_time_s':10,'max_Co':job.get('max_observed_co'),'elapsed_s':job.get('elapsed'),'eta_s':job.get('eta')})
    if extra: row.update(extra)
    status_file.write_text(json.dumps(row,indent=2),encoding='utf-8')
try:
    for number,(model,target,dt,purpose) in enumerate(plan,1):
        if any(row['round']==number and row['result']=='PASS' for row in ledger['rounds']): continue
        name=f'OFF_LONG_QA_R{number}_{stamp}'; known=next((j for j in engine.store.all() if j['name']==name),None)
        job=known or engine.enqueue(Project(name=name,turbulence=model,viscosity=1/target,end_time=10.,delta_t=dt,write_interval=.5,cores=4))
        print(f'ROUND {number}/8 START {model} Re={target} endTime=10s',flush=True)
        pause=None; deadline=time.time()+1800; last_report=0
        while True:
            jobs=engine.tick(); job=next(j for j in jobs if j['id']==job['id']); status('SOLVING',number,job)
            if job['state'] in ('FAILED','STALLED','CANCELLED'): raise RuntimeError(json.dumps({k:job.get(k) for k in ('name','state','log_tail','check_tail','failure')},indent=2))
            if number==3 and job['state']=='RUNNING' and job.get('time',0)>.1 and pause is None:
                engine.signal(job,'STOP'); time.sleep(.3); before=parse_log(Path(job['case'])/'log.solver',10.)['time']; time.sleep(1); after=parse_log(Path(job['case'])/'log.solver',10.)['time']; engine.signal(job,'CONT'); assert before==after
                pause={'before_s':before,'after_1s_s':after,'continued':True}
            if job['state']=='DONE': break
            if time.time()>deadline: raise TimeoutError('Round exceeded 1800 seconds; case remains recoverable in queue.')
            if time.time()-last_report>60: print(f'ROUND {number}: {job["state"]} t={job.get("time",0):.6g}/10s maxCo={job.get("max_observed_co")}',flush=True); last_report=time.time()
            app.processEvents(); time.sleep(.4)
        status('POSTPROCESS',number,job); case=Path(job['case']); report_dir=out/f'round{number}'; report_dir.mkdir(exist_ok=True)
        log=(case/'log.solver').read_text(errors='replace'); assert re.search(r'^End\s*$',log,re.M) and not failure_signals(log)
        co=[float(x) for x in re.findall(r'Courant Number mean:.*?max:\s*([\d.eE+-]+)',log)]; assert co and max(co)<=.3000001
        result=Result(case/(name+'.foam')); assert result.internal.GetNumberOfCells()==5120; expected=np.arange(0,10.0001,.5); assert np.allclose(result.times,expected,rtol=0,atol=1e-8)
        extrema={}; fields=('U','p')+MODELS[model].fields
        for index in range(len(result.times)):
            result.select(index)
            for field in fields:
                array=result.internal.GetCellData().GetArray(field); assert array is not None,(number,field)
                values=vtk_to_numpy(array); assert np.isfinite(values).all(),(number,index,field)
                row=extrema.setdefault(field,{'min':float('inf'),'max':float('-inf')}); row['min']=min(row['min'],float(values.min())); row['max']=max(row['max'],float(values.max()))
        result.csv(report_dir/'fields.csv',['x','y','z','t','U_x','U_y','U_z','p'],stride=8,all_times=True)
        result.mat(report_dir/'PINN.mat'); mat=loadmat(report_dir/'PINN.mat'); assert mat['xyztuvwp'].shape==(21*5120,8) and mat['xytuvp'].shape==(21*5120,6); assert np.isfinite(mat['xyztuvwp']).all()
        viewer.set_result(result); viewer.field.setCurrentIndex(viewer.field.findData('p')); viewer.slice.setCurrentIndex(viewer.slice.findData('XY mid-slice')); viewer.time_changed(20); viewer.fit(); viewer.show(); app.processEvents(); viewer.image().save(report_dir/'pressure.png'); viewer.gif(str(report_dir/'pressure.gif')); viewer.hide()
        q=audit(case)[0]; assert q['nonpositive_cells']==0 and q['max_skewness']<=.5 and q['max_nonorthogonality_deg']<=30
        force_files=list((case/'postProcessing').rglob('*forceCoeffs*.dat')); force_files=force_files or list((case/'postProcessing').rglob('coefficient*.dat')); assert force_files
        force=np.loadtxt(force_files[0],comments='#'); assert len(force)>10 and np.isfinite(force).all() and force[-1,0]>=9.999
        row={'round':number,'result':'PASS','purpose':purpose,'model':model,'Re':target,'cells':5120,'cores':4,'end_time_s':10.,'max_internal_dt_s':dt,'max_observed_Co':max(co),'genuine_frames':21,'field_times_s':result.times,'required_fields':list(fields),'finite_all_fields_all_frames':True,'field_extrema':extrema,'quality':q,'mat_3d_shape':[21*5120,8],'force_samples':len(force),'solver_elapsed_s':job.get('elapsed'),'pause_resume':pause,'case':str(case),'exports':str(report_dir),'review':'No pipeline defect observed in this round. Physical model/mesh adequacy remains unverified.'}
        ledger['rounds'].append(row); persist(); status('ROUND_PASS',number,job); print(f'ROUND {number}/8 PASS: 10s, 21 genuine frames, all required fields finite, CSV/MAT/PNG/GIF verified',flush=True)
    ledger['eight_rounds_passed']=len(ledger['rounds'])==8; persist(); status('DONE',8,extra={'eight_rounds_passed':True}); print('EIGHT >=10s FULL PIPELINE ROUNDS PASS',flush=True)
except Exception:
    failure={'round':number,'time':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'traceback':traceback.format_exc()}; ledger['failures'].append(failure); persist(); status('FAILED',number,job,{'error':failure['traceback']}); print(failure['traceback'],flush=True); raise
finally:
    viewer.play_timer.stop(); viewer.renderer.RemoveAllViewProps(); viewer.widget.Finalize(); viewer.close()
