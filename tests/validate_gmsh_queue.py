"""Exercise concurrent Qt-worker meshing and two simultaneous MPI cases."""
import sys,time,json,os
os.environ['OFF_LANGUAGE']='en'
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project
from off.backend import BASE

app=QApplication(sys.argv); w=MainWindow(); w.timer.stop(); errors=[]
w.error=lambda x:errors.append(x); tag=time.strftime('%Y%m%d_%H%M%S'); names=[]
for k,method,dim,size,skew,angle in [
    (1,'Gmsh triangle / prism',2,1.,.5,30.),
    (2,'Gmsh quadrilateral / prism',2,.5,1.,30.),
    (3,'Gmsh tetrahedral',3,1.,1.,70.),
]:
    w.project=Project(name=f'OFF_GUI_GMSH_{k}_{tag}',mesh_method=method,dimension=dim,cell_size=size,skew_limit=skew,nonortho_limit=angle)
    names.append(w.project.name); w.enqueue(True)
w.project=Project(name=f'OFF_GUI_BLOCKS_{tag}',mesh_method='Structured partitioned box',shapes=[],xmin=-2.,xmax=2.,ymin=-2.,ymax=2.,regions=[{'x':-1.,'y':-1.,'width':2.,'height':2.,'size':.25,'direction':'x+','ratio':2.}])
names.append(w.project.name); w.enqueue(True)
deadline=time.time()+180
while w.workers:
    QTest.qWait(100)
    if time.time()>deadline: raise TimeoutError('Qt-worker mesh creation timed out')
assert not errors,errors
while True:
    jobs=w.engine.tick(); own=[j for j in jobs if j['name'] in names]
    if any(j['state']=='FAILED' for j in own): raise RuntimeError(json.dumps(own,indent=2))
    if len(own)==4 and all(j['state']=='DONE' for j in own): break
    QTest.qWait(150)
    if time.time()>deadline: raise TimeoutError('Mesh checks timed out')
meshes=[{'name':j['name'],'method':j['project']['mesh_method'],'threshold_skew':j['project']['skew_limit'],'threshold_nonortho':j['project']['nonortho_limit'],'quality':j['quality'],'state':j['state']} for j in own]
names=[]
for k in range(2):
    p=Project(name=f'OFF_PARALLEL_{k}_{tag}',cores=2,end_time=.1,delta_t=.0005,write_interval=.05)
    names.append(p.name); w.engine.enqueue(p)
seen_parallel=False; highest=0; deadline=time.time()+150
while True:
    jobs=w.engine.tick(); own=[j for j in jobs if j['name'] in names]
    running=[j for j in own if j['state']=='RUNNING']; reserved=sum(j['project']['cores'] for j in own if j['state'] in ('STARTING','MESHING','CHECKING','RUNNING','PAUSED','EXPORTING'))
    highest=max(highest,reserved); seen_parallel |= len(running)==2
    if any(j['state']=='FAILED' for j in own): raise RuntimeError(json.dumps(own,indent=2))
    if all(j['state']=='DONE' for j in own): break
    QTest.qWait(50)
    if time.time()>deadline: raise TimeoutError('Parallel MPI test timed out')
assert seen_parallel and highest==4,(seen_parallel,highest)
report={'concurrent_qt_worker_gmsh_passed':True,'meshes':meshes,'two_simultaneous_mpi_cases':True,'max_reserved_cores':highest,'parallel_cases':[{'name':j['name'],'cores':2,'state':j['state'],'elapsed':j['elapsed']} for j in own],'errors':errors}
(BASE/'evidence'/'additional_validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
while w.workers: QTest.qWait(50)
w.close()
