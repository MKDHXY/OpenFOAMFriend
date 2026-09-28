"""Two engineer rounds through actual parent/leaf mouse and keyboard routes."""
import os,sys,time,json,copy,re
from pathlib import Path
os.environ['OFF_LANGUAGE']='zh';BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication,QScrollArea
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.backend import write_case,DATA
from off.models import Project
from off.workbench import signature,PHYSICS_KEYS,MESH_KEYS
app=QApplication([]);w=MainWindow();w.show();w.timer.stop();errors=[];w.error=errors.append
out=BASE/'evidence/workspace_click_QA';out.mkdir(parents=True,exist_ok=True);checks=[]
def pump(ms=70):
 end=time.time()+ms/1000
 while time.time()<end:app.processEvents();time.sleep(.005)
while w.workers:pump()
def row(tag):
 def walk(item):
  if item.data(0,Qt.UserRole)==tag:return item
  for i in range(item.childCount()):
   found=walk(item.child(i))
   if found is not None:return found
 return walk(w.tree.topLevelItem(0))
def click(tag,double=False,keyboard=False):
 item=row(tag);assert item is not None,tag;w.tree.scrollToItem(item);pump();r=w.tree.visualItemRect(item);pt=QPoint(min(r.left()+55,w.tree.viewport().width()-12),r.center().y())
 if keyboard:w.tree.setCurrentItem(item);w.tree.setFocus();QTest.keyClick(w.tree,Qt.Key_Return)
 else:QTest.mouseClick(w.tree.viewport(),Qt.LeftButton,pos=pt)
 pump()
 if double:QTest.mouseDClick(w.tree.viewport(),Qt.LeftButton,pos=pt);pump()
 assert app.activeModalWidget() is None
 route=tag[1];assert w.tabs.currentIndex()==(1 if route=='results' else 0);assert w.inspector_stack.currentIndex()==2 and w.workspace_properties.isVisible();assert w.workspace_properties.pages.currentIndex()=={'physics':0,'solver':1,'results':2}[route]
panel=w.workspace_properties
# Engineer 1: every parent and summary from every stage, both interface modes.
for guided in (False,True):
 w.set_guided(guided)
 for start in (0,1,2):
  for route in ('physics','solver','results'):
   for kind in ('nav','nav_detail'):
    w.tabs.setCurrentIndex(start);click((kind,route));checks.append(dict(round=1,from_stage=start,guided=guided,kind=kind,route=route,result='PASS'))
# Hidden / floating properties, manual mode, keyboard, and repeated double clicks.
w.open_manual_topology();w.inspector_dock.hide();click(('nav_detail','physics'))
w.inspector_dock.setFloating(True);pump();w.inspector_dock.hide();click(('nav_detail','solver'));w.inspector_dock.setFloating(False)
for route in ('physics','solver','results'):click(('nav_detail',route),double=True);click(('nav_detail',route),keyboard=True)
# No empty scene silently masquerades as data.
assert not panel.result_buttons['mat'][0].isEnabled() and '尚未' in panel.result_info.text()
# Engineer 2: real typing / Apply affects actual dictionaries and signatures.
def number(key,value):
 x=panel.fields[key];panel.pages.currentWidget().findChild(QScrollArea).ensureWidgetVisible(x);pump();x.setFocus();x.selectAll();QTest.keyClicks(x,str(value));QTest.keyClick(x,Qt.Key_Tab);pump()
click(('nav_detail','physics'));number('velocity',.9);number('viscosity',.0045);number('turbulence_intensity',.02);QTest.mouseClick(panel.buttons['physics'],Qt.LeftButton);pump();assert w.project.velocity==.9 and w.project.viscosity==.0045
click(('nav_detail','solver'));before_physics=signature(w.project,PHYSICS_KEYS);before_mesh=signature(w.project,MESH_KEYS)
for key,value in [('end_time',.12),('delta_t',.0005),('write_interval',.02),('max_co',.25),('cores',4),('n_outer_correctors',3),('n_correctors',3),('n_nonorthogonal_correctors',0)]:number(key,value)
panel.pages.currentWidget().findChild(QScrollArea).ensureWidgetVisible(panel.fields['momentum_predictor']);pump();QTest.mouseClick(panel.fields['momentum_predictor'],Qt.LeftButton,pos=QPoint(8,panel.fields['momentum_predictor'].height()//2));QTest.mouseClick(panel.buttons['solver'],Qt.LeftButton);pump();assert w.project.n_outer_correctors==3 and not w.project.momentum_predictor,(panel.feedback.text(),w.project.n_outer_correctors,w.project.momentum_predictor)
assert before_physics!=signature(w.project,PHYSICS_KEYS) and before_mesh==signature(w.project,MESH_KEYS)
case=write_case(w.project,w.profile,preview_root=out/'generated_from_clicks');fv=(case/'system/fvSolution').read_text();cd=(case/'system/controlDict').read_text();dp=(case/'system/decomposeParDict').read_text();assert re.search(r'nOuterCorrectors\s+3;',fv) and re.search(r'nCorrectors\s+3;',fv) and re.search(r'nNonOrthogonalCorrectors\s+0;',fv) and re.search(r'momentumPredictor\s+no;',fv);assert re.search(r'writeInterval\s+0.02;',cd) and re.search(r'numberOfSubdomains\s+4;',dp)
w.project.save(out/'applied_project.off.json');loaded=Project.load(out/'applied_project.off.json');assert loaded.n_outer_correctors==3 and loaded.write_interval==.02
# User-visible validation must refuse unsupported Co without mutating the project.
number('max_co',.5);QTest.mouseClick(panel.buttons['solver'],Qt.LeftButton);pump();assert w.project.max_co==.25 and '未应用' in panel.feedback.text();number('max_co',.25)
# Drafts survive page navigation/language/poll; apply has not been pressed for 5.
number('n_outer_correctors',5);click(('nav_detail','physics'));w.change_language('en');pump();click(('nav_detail','solver'));assert panel.fields['n_outer_correctors'].value()==5 and w.project.n_outer_correctors==3
w.poll()
while w.workers:pump()
assert panel.fields['n_outer_correctors'].value()==5 and w.inspector_stack.currentIndex()==2
number('n_outer_correctors',3)
# All advertised models are available; exact code and additional fields change with choice.
click(('nav_detail','physics'));combo=panel.fields['turbulence'];combo.setFocus();QTest.keyClick(combo,Qt.Key_Home);target=combo.findData('kOmegaSST')
for _ in range(target):QTest.keyClick(combo,Qt.Key_Down)
QTest.mouseClick(panel.buttons['physics'],Qt.LeftButton);pump();assert w.project.turbulence=='kOmegaSST';case=write_case(w.project,w.profile,preview_root=out/'model_from_clicks');assert all((case/'0'/f).exists() for f in ('k','omega','nut'));assert 'kOmegaSST' in (case/'constant/momentumTransport').read_text()
QTest.keyClick(combo,Qt.Key_Home);QTest.mouseClick(panel.buttons['physics'],Qt.LeftButton);pump();assert w.project.turbulence=='laminar'
# Explicit dictionary overrides must be reported, never silently ignored.
w.project.dictionary_overrides['system/fvSolution']=fv;click(('nav_detail','solver'));number('n_outer_correctors',4);QTest.mouseClick(panel.buttons['solver'],Qt.LeftButton);pump();assert w.project.n_outer_correctors==3 and 'override' in panel.feedback.text().lower();w.project.dictionary_overrides={};number('n_outer_correctors',3)
for lang,suffix in [('zh','ZH'),('en','EN')]:
 w.change_language(lang);pump()
 for route in ('physics','solver','results'):click(('nav_detail',route));panel.grab().save(str(out/f'{route}_{suffix}.png'))
report=dict(release=BASE.name,two_engineer_rounds_passed=True,real_mouse_navigation=checks,summary_parent_keyboard_double_click=True,manual_hidden_floating_dock_recovery=True,no_data_has_explicit_disabled_actions=True,real_keyboard_apply_to_dictionaries=True,parameter_save_load=True,invalid_co_rejected=True,unapplied_draft_preserved=True,model_changed_initial_fields=True,explicit_override_conflict_reported=True,pimple_invalidates_physics_not_mesh=True,errors=errors)
(out/'two_rounds.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='real_mouse_navigation'},indent=2));assert not errors;w.close()
