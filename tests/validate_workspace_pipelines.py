"""Actual edited PIMPLE/model inputs -> 3 four-rank solves -> result action clicks."""
import sys,os,time,json,re
from pathlib import Path
os.environ['OFF_LANGUAGE']='en';BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication,QPushButton,QFileDialog,QDialogButtonBox,QLineEdit,QMessageBox
from PySide6.QtCore import Qt,QPoint,QTimer
from PySide6.QtTest import QTest
from off.gui import MainWindow,Properties
from off.models import Project
from off.manual_topology import cylinder_preset,METHODS
from scipy.io import loadmat
import numpy as np
QApplication.setAttribute(Qt.AA_DontUseNativeDialogs);app=QApplication([]);w=MainWindow();w.show();w.timer.stop();errors=[];w.error=errors.append;E=BASE/'evidence/workspace_click_QA';out=E/'actual_pipelines_v017';out.mkdir(exist_ok=True)
def pump(ms=80):
 until=time.time()+ms/1000
 while time.time()<until:app.processEvents();time.sleep(.005)
def wait():
 until=time.time()+90
 while w.workers:pump();assert time.time()<until
 assert not errors,errors
wait();names=[];stamp=time.strftime('%Y%m%d_%H%M%S')
if '--reuse' in sys.argv:
 names=[j['name'] for j in w.engine.store.all() if j['name'].startswith('OFF_BINDING_')]
 assert len(names)==3
else:
 for i in range(3):
  source=E/'applied_project.off.json' if i<2 else E/'model_from_clicks/off_project.json';p=Project.load(source);p.name=f'OFF_BINDING_R{i+1}_{stamp}';p.end_time=[.04,.06,.1][i];p.write_interval=[.01,.02,.02][i]
  if i==1:p.mesh_method=METHODS[1];p.manual_mesh=cylinder_preset();p.reference_length=1
  assert p.n_outer_correctors==3 and p.n_correctors==3 and not p.momentum_predictor
  w.project=p;w.canvas.project=p;w.refresh_tree();w.tabs.setCurrentIndex(2);names.append(p.name)
  button=next(b for b in w.findChildren(QPushButton) if (b.property('off_original') or b.text())=='Submit design');QTest.mouseClick(button,Qt.LeftButton);wait()
maxcores=4 if "--reuse" in sys.argv else 0;deadline=time.time()+300
while True:
 jobs=w.engine.tick();own=[j for j in jobs if j['name'] in names];maxcores=max(maxcores,sum(j['project']['cores'] for j in own if j['state'] in ('RUNNING','MESHING','CHECKING','STARTING','EXPORTING')))
 assert not any(j['state'] in ('FAILED','STALLED') for j in own),own
 if len(own)==3 and all(j['state']=='DONE' for j in own):break
 assert time.time()<deadline;pump(200)
w.poll();wait();rows=[];panel=w.workspace_properties
# Actual modal interaction, not patched exporter callbacks.
def save_dialog(path,csv=False,directory=False):
 timer=QTimer(w);timer.setInterval(80)
 def choose():
  dialog=app.activeModalWidget()
  if isinstance(dialog,Properties) and csv:
   x=dialog.inputs['columns'];x.setFocus();x.selectAll();QTest.keyClicks(x,'x,y,z,t,U_x,U_y,U_z,p');c=dialog.inputs['times'];c.setFocus();QTest.keyClick(c,Qt.Key_End);box=dialog.findChild(QDialogButtonBox);QTest.mouseClick(box.button(QDialogButtonBox.Ok),Qt.LeftButton);return
  if isinstance(dialog,QFileDialog):
   if directory:dialog.setDirectory(str(path))
   else:
    dialog.setDirectory(str(path.parent));x=dialog.findChild(QLineEdit,'fileNameEdit');assert x is not None;x.setFocus();x.selectAll();QTest.keyClicks(x,path.name);QTest.keyClick(x,Qt.Key_Tab)
   box=dialog.findChild(QDialogButtonBox);button=next(b for b in box.buttons() if box.buttonRole(b)==QDialogButtonBox.AcceptRole);QTest.mouseClick(button,Qt.LeftButton)
  elif isinstance(dialog,QMessageBox) and dialog.standardButtons()&QMessageBox.Yes:QTest.mouseClick(dialog.button(QMessageBox.Yes),Qt.LeftButton)
 timer.timeout.connect(choose);timer.start();return timer
for i,name in enumerate(names):
 job=next(j for j in w.jobs if j['name']==name);w.jobtable.selectRow(next(j for j,x in enumerate(w.jobs) if x['name']==name));w.open_workspace_properties('results');pump();assert panel.result_buttons['load'][0].isEnabled();QTest.mouseClick(panel.result_buttons['load'][0],Qt.LeftButton);wait();r=w.viewer.result;assert r.internal.GetNumberOfCells()==5120 and len(r.times)==[5,4,6][i]
 for key,field in [('mesh','Mesh'),('pressure','p')]:panel.pages.widget(2).ensureWidgetVisible(panel.result_buttons[key][0]);pump();QTest.mouseClick(panel.result_buttons[key][0],Qt.LeftButton);pump();assert w.viewer.field.currentData()==field,(key,panel.result_buttons[key][0].isEnabled(),w.viewer.field.currentData(),panel.isVisible())
 folder=out/f'round{i+1}';folder.mkdir(exist_ok=True);w.viewer.image().save(folder/'pressure.png')
 for key,filename in [('mat','PINN.mat'),('csv','fields.csv'),('gif','fields.gif')]:
  panel.pages.widget(2).ensureWidgetVisible(panel.result_buttons[key][0]);pump();assert panel.result_buttons[key][0].isEnabled() and panel.result_buttons[key][0].isVisible();timer=save_dialog(folder/filename,csv=key=='csv');QTest.mouseClick(panel.result_buttons[key][0],Qt.LeftButton);wait();timer.stop();assert (folder/filename).is_file(),filename
 mat=loadmat(folder/'PINN.mat');assert mat['xytuvp'].shape==(len(r.times)*5120,6) and np.isfinite(mat['xyztuvwp']).all();assert np.allclose(np.unique(mat['xytuvp'][:,2]),r.times)
 csv=np.genfromtxt(folder/'fields.csv',delimiter=',',skip_header=1);assert csv.shape==(len(r.times)*5120,8) and np.isfinite(csv).all()
 fv=(Path(job['case'])/'system/fvSolution').read_text();assert re.search(r'nOuterCorrectors\s+3;',fv) and re.search(r'momentumPredictor\s+no;',fv)
 log=(Path(job['case'])/'log.solver').read_text();co=max(map(float,re.findall(r'Courant Number mean:.*?max:\s*([\d.eE+-]+)',log)));assert co<=.25 and 'End' in log
 rows.append(dict(case=name,case_folder=job['case'],model=job['project']['turbulence'],mesh_method=job['project']['mesh_method'],cells=5120,ranks=4,end_time_s=r.times[-1],genuine_frames=len(r.times),PIMPLE=dict(outer=3,pressure=3,nonorthogonal=0,momentum_predictor=False),max_observed_Co=co,quality=job['quality'],MAT_shape=list(mat['xytuvp'].shape),CSV_shape=list(csv.shape),finite=True,state=job['state']))
# Complete .foam export invokes the real button and real directory dialog once.
exports=out/'foam_export';exports.mkdir(exist_ok=True);panel.pages.widget(2).ensureWidgetVisible(panel.result_buttons['foam'][0]);pump();timer=save_dialog(exports,directory=True);QTest.mouseClick(panel.result_buttons['foam'][0],Qt.LeftButton);wait();timer.stop();exported=next(exports.glob('*_export_*'));foam=next(exported.glob('*.foam'));assert (exported/'constant/polyMesh/points').exists()
from off.post import Result
copy=Result(foam);assert copy.internal.GetNumberOfCells()==5120 and np.allclose(copy.times,w.viewer.result.times)
for lang,suffix in [('zh','ZH'),('en','EN')]:
 w.change_language(lang);w.open_workspace_properties('results');pump();panel.grab().save(str(E/f'results_loaded_{suffix}.png'))
events=[];intervals=[]
for job in own:
 case=Path(job['case']);start=int((case/'off.start').read_text());end=int((case/'off.end').read_text());intervals.append(dict(case=job['name'],start_unix_s=start,end_unix_s=end,ranks=job['project']['cores']));events.extend([(start,job['project']['cores']),(end,-job['project']['cores'])])
reserved=0;maxcores=0
for timestamp,delta in sorted(events,key=lambda e:(e[0],e[1])):reserved+=delta;maxcores=max(maxcores,reserved)
report=dict(release=BASE.name,reused_completed_cases_after_UI_only_fix=('--reuse' in sys.argv),three_real_3D_four_rank_pipelines_passed=True,max_reserved_cores=maxcores,actual_driver_intervals=intervals,rounds=rows,result_buttons_real_dialog_exports=True,complete_foam_export_verified=str(exported),errors=errors);(E/'pipeline_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));assert maxcores==4;wait();w.close()
