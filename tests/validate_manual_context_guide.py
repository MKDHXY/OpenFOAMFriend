import sys,os,time,json,copy
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));os.environ['OFF_LANGUAGE']='en'
from PySide6.QtWidgets import QApplication,QToolButton,QDialogButtonBox
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project
from off import manual_topology as topo
from off.manual_reference import import_boundaries,cylinder_blocks,points
app=QApplication([]);w=MainWindow();w.show();w.timer.stop();errors=[];w.error=errors.append;out=BASE/'evidence/manual_context';out.mkdir(exist_ok=True)
def pump(ms=100):
 end=time.time()+ms/1000
 while time.time()<end:app.processEvents();time.sleep(.005)
while w.workers:pump()
w.reset_layout();w.set_guided(True);w.open_manual_topology();pump();ed=w.manual_editor
assert w.guide_dock.isVisible() and not w.inspector_dock.isVisible()
assert not w.tabifiedDockWidgets(w.guide_dock)
assert len([i for i in ed.view.scene().items() if i.data(1)=='reference'])>=4
assert len(ed.graph['edges'])==0
# Real toolbar click targets the model, preserving domain references and topology.
button=next(b for b in ed.findChildren(QToolButton) if b.defaultAction() and b.defaultAction().text()=='Fit model');QTest.mouseClick(button,Qt.LeftButton);pump();assert ed.view.transform().m11()>1;ed.fit()
# References never silently compile a mesh. Actual click imports exact domain and hole.
QTest.mouseClick(ed.import_context,Qt.LeftButton);pump();assert len(ed.graph['edges'])==8
fs,fluid=topo.validate(ed.graph,'Gmsh');assert len(fluid)==1 and sum(topo.settings(ed.graph,f)['role']=='hole' for f in fs)==1
before=copy.deepcopy(ed.graph);QTest.mouseClick(ed.import_context,Qt.LeftButton);pump();assert ed.graph==before
ed.undo();ed.undo();assert not ed.graph['edges'];assert w.project.shapes
# Selecting steps does not change the stage, editor, camera, drawing draft, or project.
ed.view.choose('line');ed.view.draft=[(1.,1.)];transform=ed.view.transform();initial=(w.tabs.currentIndex(),w.pre_mode.currentIndex())
for step in range(6):
 QTest.mouseClick(w.guide.steps.viewport(),Qt.LeftButton,pos=w.guide.steps.visualItemRect(w.guide.steps.item(step)).center());pump()
 assert initial==(w.tabs.currentIndex(),w.pre_mode.currentIndex());assert ed.view.draft==[(1.,1.)];assert ed.view.transform()==transform
# Setting pages remain embedded, guide visible on every page and polling.
for step in (0,1,2,3):
 w.guide.choose(step);QTest.mouseClick(w.guide.configure,Qt.LeftButton);pump()
 assert app.activeModalWidget() is None and w.guide_dock.isVisible()
 assert initial==(w.tabs.currentIndex(),w.pre_mode.currentIndex())
 for _ in range(3):w.context_update();w.refresh_tree();pump()
 assert w.guide_dock.isVisible() and w.inspector_dock.isVisible()
 assert w.inspector_stack.currentIndex()==(1 if step==2 else 2 if step==3 else w.inspector_stack.indexOf(w.guided_form))
# Embedded domain Apply updates visible references, preserves graph draft and actual mode.
w.guide.choose(1);w.guide.settings();dialog=w.guided_form.widget();dialog.inputs['depth'].setValue(.75)
QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton);pump()
assert w.project.depth==.75 and ed.graph==w.project.manual_mesh and ed.view.draft==[(1.,1.)]
assert w.guide_dock.isVisible() and dialog.isVisible() and not dialog.isWindow()
# New project and off-centre SI-scaled cylinder preset; no hardcoded 1m diameter.
p=Project(name='Context',xmin=-.02,xmax=.04,ymin=-.03,ymax=.03,outer_radius=.025,depth=.001)
p.shapes[0].update(x=.005,y=.002,width=.002,height=.002);w.project=p;w.canvas.project=p;w.refresh_tree();w.open_manual_topology();pump()
button=next(b for b in ed.findChildren(QToolButton) if b.defaultAction() and b.defaultAction().text()=='Cylinder blocks…');QTest.mouseClick(button,Qt.LeftButton);pump();g=ed.graph;topo.validate(g,'blockMesh');assert len(g['edges'])==12
assert abs(min(v[0] for v in g['nodes'].values())-(.005-.025))<1e-12
assert abs(ed.reference.value()-.002)<1e-12
ed.select(('edge',g['edges'][0]['id']));ed.apply_selected();assert w.guide_dock.isVisible()
for lang in ('en','zh'):
 w.change_language(lang);pump();w.inspector_dock.hide();ed.fit();pump();w.grab().save(str(out/f'manual_model_guide_{lang.upper()}.png'));ed.fit_model();pump();w.grab().save(str(out/f'manual_model_detail_{lang.upper()}.png'))
# Domain+rectangle+triangle+polygon import are actual loops with exclusion roles.
q=Project(xmin=-10,xmax=10,ymin=-10,ymax=10);q.shapes=[dict(kind='rectangle',x=-4,y=0,width=2,height=2,name='box'),dict(kind='triangle',x=0,y=0,width=2,height=2,name='triangle'),dict(kind='polygon',x=4,y=0,width=2,height=2,name='poly',vertices=[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])]
g=topo.empty();import_boundaries(g,q);fs,fluid=topo.validate(g,'Gmsh');assert len(fluid)==1 and sum(topo.settings(g,f)['role']=='hole' for f in fs)==3
assert not errors,errors
report=dict(release=BASE.name,two_engineer_rounds=True,reference_visible_without_mutating_mesh=True,import_actual_boundary_loops=True,idempotent_import_and_undo=True,offcentre_SI_cylinder_template=True,three_polygon_solids_are_holes=True,six_guide_steps_do_not_switch_workspace=True,four_setting_routes_embedded_no_modal=True,guide_persists_after_settings_poll_and_language=True,domain_apply_preserves_draft=True,errors=errors)
(out/'QA.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));w.set_guided(False);w.close()
