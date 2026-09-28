"""Recover a real stopped MPI case from matching saved rank fields."""
import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from off.backend import Engine,BASE
from off.models import Profile,Project
e=Engine(Profile()); p=Project(name='OFF_CHECKPOINT_'+time.strftime('%Y%m%d_%H%M%S'),end_time=.5,delta_t=.0005,write_interval=.05)
j=e.enqueue(p); deadline=time.time()+120
while True:
    j=next(x for x in e.tick() if x['id']==j['id'])
    if j['state']=='RUNNING' and j.get('time',0)>.07: break
    if j['state'] in ('FAILED','DONE'): raise RuntimeError('Unexpected state before checkpoint interruption: '+j['state'])
    if time.time()>deadline: raise TimeoutError('No checkpoint progress')
    time.sleep(.2)
e.signal(j,'TERM'); time.sleep(1)
case=Path(j['case']); j['state']='STALLED'; (case/'off.state').write_text('STALLED'); e.store.save(j)
e.resume_saved(j); resumed=j['resumed_from']
assert resumed>=.05 and resumed<p.end_time
while True:
    j=next(x for x in e.tick() if x['id']==j['id'])
    if j['state']=='DONE': break
    if j['state']=='FAILED': raise RuntimeError((case/'log.solver').read_text()[-1800:])
    if time.time()>deadline: raise TimeoutError('Recovery timed out')
    time.sleep(.2)
assert j['time']==.5
report={'checkpoint_recovery_passed':True,'case':j['name'],'cores':4,'complete_checkpoint_time_s':resumed,'final_time_s':j['time'],'state':j['state'],'fault':'TERM only the verified validation-case MPI tree; no host reboot','remeshed':False}
(BASE/'evidence'/'checkpoint_validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
