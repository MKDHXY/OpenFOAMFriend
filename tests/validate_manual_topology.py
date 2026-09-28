"""Real mouse drafting and actual manual topology -> mesh -> four-rank flow -> exports."""
import os,sys,time,json,copy
from pathlib import Path
os.environ['OFF_LANGUAGE']='zh';BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication,QToolButton,QScrollArea,QPushButton
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from off.models import Project
from off.gui import MainWindow
from off import manual_topology as topo
from scipy.io import loadmat
import numpy as np
app=QApplication([]);w=MainWindow();w.show();w.timer.stop();errors=[];w.error=errors.append;out=BASE/'evidence/manual_topology';out.mkdir(exist_ok=True)
def pump(ms=100):
 end=time.monotonic()+ms/1000
 while time.monotonic()<end:app.processEvents();time.sleep(.01)
def wait():
 deadline=time.time()+180
 while w.workers:pump(50);assert time.time()<deadline
 assert not errors,errors
wait();QTest.mouseClick(w.pre_mode,Qt.LeftButton,pos=w.pre_mode.tabRect(2).center());pump();ed=w.manual_editor;c=ed.view
assert w.design_stack.currentIndex()==2 and not w.sketch_toolbar.isVisible()
# Toolbar, two-click lines, no press-and-hold drawing.
def tool(key):
 a=ed.actions[key][0];button=next(b for b in ed.findChildren(QToolButton) if b.defaultAction() is a);QTest.mouseClick(button,Qt.LeftButton);pump();assert c.tool==key
def clickxy(x,y):QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=c.mapFromScene(x,-y));pump()
def typeval(widget,value):
 widget.setFocus();widget.selectAll();QTest.keyClicks(widget,str(value));QTest.keyClick(widget,Qt.Key_Tab)
def apply():
 parent=ed.inputs[ed.selected[0],next(k for cat,k in ed.inputs if cat==ed.selected[0])].parentWidget()
 QTest.mouseClick(ed.apply,Qt.LeftButton);pump()
tool('line')
for a,b in [((-4,-2),(4,-2)),((4,-2),(4,2)),((4,2),(-4,2)),((-4,2),(-4,-2))]:clickxy(*a);clickxy(*b)
assert len(ed.graph['edges'])==4 and len(topo.faces(ed.graph))==1
# Split at two boundary nodes; line between them forms two independent conformal faces.
tool('split');clickxy(0,-2);clickxy(0,2);assert len(ed.graph['edges'])==6
tool('line');clickxy(0,-2);clickxy(0,2);assert len(topo.faces(ed.graph))==2
fs=topo.faces(ed.graph);left=min(fs,key=lambda f:sum(x for x,y in f['poly'])/len(f['poly']));right=next(f for f in fs if f is not left)
# Select actual interior of region in the canvas, then assign with real input/button events.
tool('select');clickxy(-2,0);assert ed.selected==('face',left['key']),ed.selected
for key,value in [('nx',12),('ny',8),('gx',1),('gy',1)]:typeval(ed.inputs['face',key],value)
apply();assert topo.validate(ed.graph,'blockMesh')
clickxy(2,0);assert ed.selected==('face',right['key']);typeval(ed.inputs['face','nx'],6);typeval(ed.inputs['face','ny'],8);apply();assert topo.validate(ed.graph,'blockMesh')
ed.grab().save(str(out/'manual_region_assignment_ZH.png'))
# Eraser deletes only the split edge between its two nodes, not an entire polyline.
before=len(ed.graph['edges']);tool('erase');clickxy(-2,-2);assert len(ed.graph['edges'])==before-1
QTest.keyClick(c,Qt.Key_Z,Qt.ControlModifier);pump();assert len(ed.graph['edges'])==before
QTest.keyClick(c,Qt.Key_Y,Qt.ControlModifier);pump();assert len(ed.graph['edges'])==before-1
QTest.keyClick(c,Qt.Key_Z,Qt.ControlModifier);pump();assert len(ed.graph['edges'])==before
# New independent draft checks a true three-point arc and arc-aware split.
p=Project();w.project=p;w.canvas.project=p;w.refresh_tree();ed.reload();ed.fit();tool('arc')
for xy in [(-2,0),(0,2),(2,0)]:clickxy(*xy)
assert len(ed.graph['edges'])==1 and ed.graph['edges'][0]['kind']=='arc'
original=copy.deepcopy(ed.graph);tool('split');clickxy(0,2);assert len(ed.graph['edges'])==2 and all(e['kind']=='arc' for e in ed.graph['edges'])
assert abs(sum(abs(topo.arc_geometry(ed.graph,e)[4]) for e in ed.graph['edges'])-abs(topo.arc_geometry(original,original['edges'][0])[4]))<1e-6
# Arc through-point and coordinates are preserved by SI project save/load.
save=out/'arc_draft.off.json';w.project.save(save);assert Project.load(save).manual_mesh==w.project.manual_mesh
w.change_language('en');pump();assert ed.actions['split'][0].text()=='Split at point';ed.grab().save(str(out/'manual_arc_split_EN.png'));w.change_language('zh')
# Bad open topology cannot be activated or submitted.
assert not ed.activate() and '开口' in ed.feedback.text()
# Three genuine full pipelines with independently drafted cylinder blocks, not old automatic O-grid.
names=[];stamp=time.strftime('%Y%m%d_%H%M%S')
for i in range(3):
 graph=topo.cylinder_preset()
 if i==2:
  f=next(f for f in topo.faces(graph) if topo.settings(graph,f)['role']=='fluid');topo.assign(graph,f['key'],16,21,1,1)
 p=Project(name=f'OFF_TOPOLOGY_R{i+1}_{stamp}',manual_mesh=graph,reference_length=1,end_time=[.05,.08,1][i],delta_t=.0005,write_interval=[.01,.02,.1][i])
 w.project=p;w.canvas.project=p;w.refresh_tree();w.open_manual_topology();ed.backend.setCurrentIndex(1 if i==1 else 0)
 QTest.mouseClick(ed.activate_button,Qt.LeftButton);pump();assert w.project.mesh_method==topo.METHODS[1 if i==1 else 0]
 w.project.save(out/f'round{i+1}.off.json');names.append(p.name);w.tabs.setCurrentIndex(2);pump();submit=next(b for b in w.findChildren(QPushButton) if (b.property('off_original') or b.text())=='Submit design');QTest.mouseClick(submit,Qt.LeftButton);wait()
paused=False;pause=None;deadline=time.time()+300;maxcores=0
from off.backend import parse_log
while True:
 jobs=w.engine.tick();own=[j for j in jobs if j['name'] in names];maxcores=max(maxcores,sum(j['project']['cores'] for j in own if j['state'] in ('RUNNING','MESHING','CHECKING','PAUSED','STARTING','EXPORTING')))
 third=next(j for j in own if j['name']==names[2])
 if third['state']=='RUNNING' and third.get('time',0)>.001 and not paused:
  w.engine.signal(third,'STOP');pump(200);before=parse_log(Path(third['case'])/'log.solver',1)['time'];pump(1000);after=parse_log(Path(third['case'])/'log.solver',1)['time'];assert before==after;w.engine.signal(third,'CONT');paused=True;pause=dict(before=before,after=after)
 assert not any(j['state'] in ('FAILED','STALLED') for j in own),own
 if len(own)==3 and all(j['state']=='DONE' for j in own):break
 assert time.time()<deadline,'Three manual pipelines timeout';pump(150)
assert maxcores==4 and paused
w.poll();wait();rows=[]
for i,name in enumerate(names):
 job=next(j for j in w.jobs if j['name']==name);row=next(r for r,j in enumerate(w.jobs) if j['name']==name);w.jobtable.selectRow(row);button=next(b for b in w.findChildren(QPushButton) if (b.property('off_original') or b.text())=='Open result');QTest.mouseClick(button,Qt.LeftButton);wait();result=w.viewer.result;assert result is not None
 expected=5376 if i==2 else 5120;assert result.internal.GetNumberOfCells()==expected;assert len(result.times)==[6,5,11][i]
 folder=out/f'round{i+1}_export';folder.mkdir(exist_ok=True);result.mat(folder/'PINN.mat');result.csv(folder/'fields.csv',['x','y','z','t','U_x','U_y','U_z','p'],stride=4,all_times=True);w.viewer.image().save(folder/'field.png');w.viewer.gif(str(folder/'fields.gif'));m=loadmat(folder/'PINN.mat');assert m['xytuvp'].shape==(expected*len(result.times),6) and np.isfinite(m['xyztuvwp']).all()
 rows.append(dict(case=name,method=job['project']['mesh_method'],cells=expected,cores=4,simulated_time_s=result.times[-1],frames=len(result.times),quality=job['quality'],MAT_rows=m['xytuvp'].shape[0],finite=True,case_folder=job['case'],max_observed_Co=job.get('max_co'),state='DONE'))
 w.viewer.image().save(out/f'round{i+1}_mesh_result.png')
w.open_manual_topology();ed.select(('face',next(f['key'] for f in topo.faces(ed.graph) if topo.settings(ed.graph,f)['role']=='fluid')));w.change_language('zh');ed.grab().save(str(out/'manual_editor_ZH.png'));w.change_language('en');ed.grab().save(str(out/'manual_editor_EN.png'))
report=dict(release=BASE.name,real_mouse_two_click_lines=True,shared_nodes_split_partition_two_regions=True,per_region_independent_assignment=True,erase_exact_segment_undo_redo=True,true_arc_three_click_and_split=True,draft_save_load_SI=True,bilingual_manual_controls=True,open_topology_blocks_activation=True,three_real_3D_four_core_pipelines=rows,pause_resume=pause,max_reserved_cores=maxcores,errors=errors)
(out/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));assert not errors;wait();w.close()
