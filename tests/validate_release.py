"""Three genuine 5120-cell, 4-rank 3D cylinder GUI-to-export tests."""
import sys,time,json,csv,os
os.environ['OFF_LANGUAGE']='en'
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.io import loadmat
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt,QPoint
from off.models import Project
from off.backend import BASE,parse_log
from off.gui import MainWindow
from off.quality import audit

app=QApplication([]); window=MainWindow(); errors=[]; window.error=lambda e:errors.append(e); window.show(); QTest.qWait(500); window.timer.stop()
out=BASE/'evidence'; out.mkdir(exist_ok=True); stamp=time.strftime('%Y%m%d_%H%M%S')

# In-process pointer interactions test the actual sketch implementation.
window.canvas.set_tool('rectangle'); a=window.canvas.mapFromScene(-100,-100); b=window.canvas.mapFromScene(-40,-40)
QTest.mousePress(window.canvas.viewport(),Qt.LeftButton,pos=a); QTest.mouseMove(window.canvas.viewport(),b,50); QTest.mouseRelease(window.canvas.viewport(),Qt.LeftButton,pos=b); assert len(window.project.shapes)==2
window.canvas.undo(); assert len(window.project.shapes)==1
window.canvas.set_tool('region'); QTest.mousePress(window.canvas.viewport(),Qt.LeftButton,pos=a); QTest.mouseMove(window.canvas.viewport(),b,50); QTest.mouseRelease(window.canvas.viewport(),Qt.LeftButton,pos=b); assert len(window.project.regions)==1
window.canvas.undo(); assert not window.project.regions

submit=next(b for b in window.findChildren(QPushButton) if b.text()=='Submit design')
window.tabs.setCurrentIndex(2)
names=[]
for i in range(3):
    p=Project(name=f'OFF_RELEASE_R{i+1}_{stamp}',end_time=[.05,.08,1.][i],delta_t=.0005,write_interval=[.01,.02,.1][i])
    p.save(out/f'round{i+1}_project.off.json'); names.append(p.name); window.project=p; window.canvas.project=p; window.canvas.rebuild(); window.refresh_tree()
    while not submit.isEnabled(): QTest.qWait(30)
    QTest.mouseClick(submit,Qt.LeftButton)
    deadline=time.time()+90
    while not any(j['name']==p.name for j in window.engine.store.all()):
        QTest.qWait(50)
        if errors: raise RuntimeError(errors[-1])
        if time.time()>deadline: raise TimeoutError('GUI submission failed')
    while window.workers: QTest.qWait(30)

paused=False; pause_evidence=None; max_reserved=0; deadline=time.time()+300
while True:
    jobs=window.engine.tick(); own=[j for j in jobs if j['name'] in names]; max_reserved=max(max_reserved,sum(j['project']['cores'] for j in own if j['state'] in ('STARTING','MESHING','CHECKING','RUNNING','PAUSED','EXPORTING')))
    third=next(j for j in own if j['name']==names[2])
    if third['state']=='RUNNING' and third.get('time',0)>.001 and not paused:
        signal=window.engine.signal(third,'STOP'); QTest.qWait(300); before=parse_log(Path(third['case'])/'log.solver',1.)['time']; QTest.qWait(1500); after=parse_log(Path(third['case'])/'log.solver',1.)['time']; assert before==after,(before,after)
        pause_evidence={'before':before,'after_1p5_seconds':after,'signal_result':signal}; window.engine.signal(third,'CONT'); paused=True
    if any(j['state'] in ('FAILED','STALLED') for j in own): raise RuntimeError(json.dumps(own,indent=2))
    if len(own)==3 and all(j['state']=='DONE' for j in own): break
    if time.time()>deadline: raise TimeoutError('Validation exceeded 300 s')
    QTest.qWait(250)
assert paused; assert max_reserved==4; window.poll(); QTest.qWait(600)
while window.workers: QTest.qWait(50)
window.canvas.fit(); window.tabs.setCurrentIndex(0); window.grab().save(str(out/'design.png'))
window.tabs.setCurrentIndex(2); window.grab().save(str(out/'queue.png'))
results=[]
for i,name in enumerate(names):
    j=next(j for j in window.engine.store.all() if j['name']==name); case=Path(j['case']); row=next(k for k,x in enumerate(window.jobs) if x['name']==name); window.jobtable.selectRow(row)
    openbtn=next(b for b in window.findChildren(QPushButton) if b.text()=='Open result'); QTest.mouseClick(openbtn,Qt.LeftButton)
    load_deadline=time.time()+60
    while window.workers:
        QTest.qWait(50)
        if errors: raise RuntimeError(errors[-1])
        if time.time()>load_deadline: raise TimeoutError('Result load exceeded 60 s')
    r=window.viewer.result; assert r is not None; assert r.internal.GetNumberOfCells()==5120; assert len(r.times)==[6,5,11][i]; assert abs(r.times[-1]-j['project']['end_time'])<1e-9
    window.viewer.field.setCurrentText('p'); window.viewer.time_changed(len(r.times)-1); window.viewer.slice.setCurrentText('XY mid-slice'); QTest.qWait(100)
    window.viewer.image().save(out/f'round{i+1}_pressure.png'); window.viewer.gif(str(out/f'round{i+1}.gif'))
    csvpath=out/f'round{i+1}.csv'; matpath=out/f'round{i+1}.mat'; r.csv(csvpath,['x','y','z','t','U_x','U_y','U_z','p'],stride=4,all_times=True); r.mat(matpath)
    m=loadmat(matpath); assert m['xytuvp'].shape==(len(r.times)*5120,6); assert m['xyztuvwp'].shape==(len(r.times)*5120,8); assert np.isfinite(m['xyztuvwp']).all(); assert len(np.unique(m['xyztuvwp'][:,2]))==4
    with csvpath.open() as f: assert sum(1 for _ in f)==len(r.times)*1280+1
    qa=audit(case); assert qa[0]['nonpositive_cells']==0; assert qa[0]['max_skewness']<.5; assert abs(qa[0]['max_skewness']-j['quality']['skewness'])<1e-7
    vtk_files=list((case/'VTK').rglob('*.vtk')); assert len(vtk_files)>0
    result={'round':i+1,'case':name,'state':j['state'],'cores':j['project']['cores'],'cells':5120,'solver_end_s':r.times[-1],'genuine_frames':len(r.times),'mat_shape':list(m['xyztuvwp'].shape),'finite':True,'quality':qa[0],'solver_elapsed_seconds':j.get('elapsed'),'vtk_file_count':len(vtk_files),'case_folder':str(case)}; results.append(result)
window.viewer.show_quality(qa); window.viewer.image().save(out/'quality.png')
report={'release':BASE.name,'three_rounds_passed':True,'max_reserved_cores':max_reserved,'pause_resume':pause_evidence,'gui_sketch_draw_undo_regions':True,'rounds':results,'errors':errors}
(out/'validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2)); window.timer.stop()
while window.workers: QTest.qWait(50)
window.close()
