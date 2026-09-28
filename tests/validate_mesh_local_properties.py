"""Second-round supplementary edge paths for local size controls and retained dialogs."""
import os,sys,time,json
from pathlib import Path
os.environ['OFF_LANGUAGE']='zh'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication,QScrollArea,QDialog
from PySide6.QtCore import Qt,QTimer,QPoint
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append
def pump(ms=100):
    end=time.monotonic()+ms/1000
    while time.monotonic()<end: app.processEvents(); time.sleep(.01)
while w.workers: pump()
def click_control(button):
    parent=button.parentWidget()
    while parent:
        if isinstance(parent,QScrollArea): parent.ensureWidgetVisible(button); break
        parent=parent.parentWidget()
    pump(); assert button.isVisible() and button.isEnabled(); QTest.mouseClick(button,Qt.LeftButton); pump()
def click_tag(tag):
    def find(item):
        if item.data(0,Qt.UserRole)==tag:return item
        for i in range(item.childCount()):
            f=find(item.child(i))
            if f is not None:return f
    item=find(w.tree.topLevelItem(0)); assert item is not None; w.tree.scrollToItem(item); pump(); r=w.tree.visualItemRect(item); QTest.mouseClick(w.tree.viewport(),Qt.LeftButton,pos=QPoint(r.left()+45,r.center().y())); pump()
w.project=Project(mesh_method='Gmsh triangle / prism'); w.canvas.project=w.project; w.canvas.rebuild(); w.refresh_tree(); click_tag(('mesh_editor','refinement')); p=w.mesh_inspector
assert p.target.currentData() is None and not p.apply_refinement_button.isEnabled() and p.draw_button.isEnabled()
click_control(p.draw_button); w.canvas.snap=0
for x,y in [(2,2),(4,4)]: QTest.mouseClick(w.canvas.viewport(),Qt.LeftButton,pos=w.canvas.mapFromScene(x*50,-y*50)); pump()
click_tag(('region',0)); assert p.target.currentData()==0 and p.apply_refinement_button.isEnabled()
p.mode.setFocus(); QTest.keyClick(p.mode,Qt.Key_End); p.direction.setFocus(); QTest.keyClick(p.direction,Qt.Key_End)
for widget,value in [(p.ratio,'2'),(p.region_fields['size'],'0.4')]:
    widget.setFocus(); widget.selectAll(); QTest.keyClicks(widget,value); QTest.keyClick(widget,Qt.Key_Tab)
click_control(p.apply_refinement_button); r=w.project.regions[0]; assert r['ratio']==.5 and r['direction']=='y-' and r['size']==.4,r
seen=[]
def reject_modal():
    dialog=app.activeModalWidget(); assert isinstance(dialog,QDialog); seen.append(dialog.windowTitle()); dialog.reject()
# Clicking the actual advanced controls still opens the original settings dialogs.
for tag,button in [('refinement',p.advanced_spacing),('generator',p.advanced_generator)]:
    click_tag(('mesh_editor',tag)); QTimer.singleShot(250,reject_modal); click_control(button)
assert len(seen)==2 and not errors
report={'release':BASE.name,'round':2,'empty_Gmsh_region_explained':True,'actual_mouse_region_draw_select_apply':r,'original_generator_and_spacing_dialogs_accessible':seen,'errors':errors}
(BASE/'evidence/navigation_click_QA/round2_local_regions.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2)); w.close()
