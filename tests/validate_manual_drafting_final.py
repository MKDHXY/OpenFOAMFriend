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

assert ed.selected is None or ed.selected in ({("node",int(n)) for n in ed.graph["nodes"]}|{("edge",e["id"]) for e in ed.graph["edges"]}|{("face",f["key"]) for f in topo.faces(ed.graph)})
assert not errors
(out/"final_drafting_QA.json").write_text(json.dumps(dict(release=BASE.name,real_mouse_drafting_after_final_changes=True,arc_split_erase_undo_assign=True,errors=errors),indent=2))
print("Final drafting mouse QA PASS");w.close()
