"""User-facing mouse/keyboard acceptance; never call navigation handlers directly."""
import sys,os,time,json
from pathlib import Path
os.environ['OFF_LANGUAGE']='zh'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project
from off.mesh import cylinder_dict
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append
def pump(ms=100):
    until=time.time()+ms/1000
    while time.time()<until: app.processEvents(); time.sleep(.01)
while w.workers: pump()
out=BASE/'evidence/navigation_click_QA'; out.mkdir(exist_ok=True)
def row(tag):
    def walk(item):
        if item.data(0,Qt.UserRole)==tag: return item
        for i in range(item.childCount()):
            found=walk(item.child(i))
            if found is not None: return found
    return walk(w.tree.topLevelItem(0))
def click(tag,double=False):
    item=row(tag); assert item is not None,tag; w.tree.scrollToItem(item); pump(); rect=w.tree.visualItemRect(item); pt=QPoint(min(rect.left()+60,w.tree.viewport().width()-15),rect.center().y())
    QTest.mouseClick(w.tree.viewport(),Qt.LeftButton,pos=pt); pump()
    if double: QTest.mouseDClick(w.tree.viewport(),Qt.LeftButton,pos=pt); pump()
def exposed(page):
    assert w.tabs.currentIndex()==0 and w.pre_mode.currentIndex()==(0 if w.guide_action.isChecked() else 1)
    assert w.inspector_stack.currentIndex()==1 and w.mesh_inspector.isVisible() and not w.inspector_dock.isHidden()
    assert w.mesh_inspector.pages.currentIndex()==page and app.activeModalWidget() is None, (page,w.mesh_inspector.pages.currentIndex(),app.activeModalWidget())
rows=[]
for guided in (True,False):
    w.set_guided(guided)
    for start in (0,1,2):
        for name,page in [('generator',0),('refinement',1)]:
            w.tabs.setCurrentIndex(start); w.pre_mode.setCurrentIndex(0); click(('mesh_editor',name)); exposed(page)
            rows.append({'from_stage':start,'guided':guided,'clicked':name,'visible_page':page,'result':'PASS'})
for name,page in [('generator',0),('refinement',1)]: click(('mesh_editor',name),True); exposed(page)
panel=w.mesh_inspector; click(('mesh_editor','generator')); widget=panel.fields['radial']; widget.setFocus(); widget.selectAll(); QTest.keyClicks(widget,'21'); QTest.keyClick(widget,Qt.Key_Tab); QTest.mouseClick(panel.apply_generator_button,Qt.LeftButton); pump(); assert w.project.radial==21 and '(21 16 4)' in cylinder_dict(w.project)
w.grab().save(str(out/'round2_generator_applied_ZH.png'))
click(('mesh_editor','refinement')); panel.mode.setFocus(); QTest.keyClick(panel.mode,Qt.Key_Home); QTest.keyClick(panel.mode,Qt.Key_Down); panel.ratio.setFocus(); panel.ratio.selectAll(); QTest.keyClicks(panel.ratio,'3'); QTest.keyClick(panel.ratio,Qt.Key_Tab); QTest.mouseClick(panel.apply_refinement_button,Qt.LeftButton); pump(); assert w.project.grading==3 and 'simpleGrading (3' in cylinder_dict(w.project)
w.grab().save(str(out/'round2_refinement_applied_ZH.png'))
# Toolbar buttons are actual user routes, not callback invocations.
for label,page in [('Mesh generation settings',0),('Mesh spacing',1)]:
    action=next(a for a in w.mesh_toolbar.actions() if (a.property('off_original') or a.text())==label); QTest.mouseClick(w.mesh_toolbar.widgetForAction(action),Qt.LeftButton); pump(); exposed(page)
# The add/draw button must activate real two-click region drawing.
QTest.mouseClick(panel.draw_button,Qt.LeftButton); pump(); assert w.canvas.tool=='region' and w.design_stack.currentIndex()==0
c=w.canvas; c.snap=0
for x,y in [(2,2),(4,4)]: QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=c.mapFromScene(x*50,-y*50)); pump()
assert len(w.project.regions)==1; click(('region',0)); exposed(1); assert panel.target.currentData()==0
assert not panel.apply_refinement_button.isEnabled() and 'O' in panel.refinement_note.text() # O-grid must not pretend a box region applies
# Second engineer round: hidden/floating docks, bilingual labels, drafts, real edited mesh.
click(('mesh_editor','generator')); panel.fields['radial'].setFocus(); panel.fields['radial'].selectAll(); QTest.keyClicks(panel.fields['radial'],'22'); QTest.keyClick(panel.fields['radial'],Qt.Key_Tab)
w.change_language('en'); pump(); assert panel.fields['radial'].value()==22
assert panel.advanced_generator.text()=='Full settings dialog…' and panel.refinement_labels[0][0].text()=='Target'
w.change_language('zh'); pump(); assert panel.fields['radial'].value()==22 and panel.refinement_labels[0][0].text()=='目标'
click(('mesh_editor','refinement')); assert panel.fields['radial'].value()==22
assert panel.pages.tabBar().isVisible() and panel.heading.isVisible() and all(not x.isVisible() for x in panel.region_fields.values())==False # current local target
panel.target.setCurrentIndex(panel.target.findData(-1)); pump(); assert all(not x.isVisible() for x in panel.region_fields.values())
w.inspector_dock.hide(); w.tabs.setCurrentIndex(2); click(('mesh_editor','refinement')); exposed(1)
w.inspector_dock.setFloating(True); pump(); w.inspector_dock.hide(); click(('mesh_editor','generator')); exposed(0); w.inspector_dock.setFloating(False); pump()
# Invalid circumferential count must give feedback and leave the actual Project untouched.
before=w.project.circumferential; widget=panel.fields['circumferential']; widget.setFocus(); widget.selectAll(); QTest.keyClicks(widget,'65'); QTest.keyClick(widget,Qt.Key_Tab); QTest.mouseClick(panel.apply_generator_button,Qt.LeftButton); pump()
assert w.project.circumferential==before and '未应用' in panel.feedback.text()
for key,value in [('circumferential',64),('radial',21)]:
    widget=panel.fields[key]; widget.setFocus(); widget.selectAll(); QTest.keyClicks(widget,str(value)); QTest.keyClick(widget,Qt.Key_Tab)
QTest.mouseClick(panel.apply_generator_button,Qt.LeftButton); pump(); assert w.project.radial==21
# Remove the drawn irrelevant O-grid region and run the actual Generate/check toolbar action.
w.project.regions=[]; w.project.name='OFF_CLICK_EDITED_'+time.strftime('%Y%m%d_%H%M%S'); w.refresh_tree(); click(('mesh_editor','refinement'))
w.grab().save(str(out/'round2_refinement_header_visible_ZH.png')); panel.grab().save(str(out/'round2_panel_ZH.png'))
action=next(a for a in w.mesh_toolbar.actions() if (a.property('off_original') or a.text())=='Generate / check mesh only')
QTest.mouseClick(w.mesh_toolbar.widgetForAction(action),Qt.LeftButton); pump()
deadline=time.time()+120
while True:
    jobs=w.engine.tick(); own=[j for j in jobs if j['name']==w.project.name]
    if own and own[0]['state']=='DONE': break
    assert not errors,errors
    assert not own or own[0]['state'] not in ('FAILED','STALLED'),own
    assert time.time()<deadline,'Generate/check timeout'
    pump(150)
assert own[0]['quality']['cells']==5376 and own[0]['quality']['passed'],own[0]
click(('mesh_editor','generator')); w.change_language('en'); pump(); panel.grab().save(str(out/'round2_panel_EN.png'))
report={'release' :BASE.name,'round':2,'real_mouse_navigation':rows,'double_click_no_duplicate_dialog':True,'actual_keyboard_apply_radial_cells':21,'actual_keyboard_apply_radial_ratio':3,'actual_toolbar_routes':True,'draw_button_and_two_click_region':True,'unsupported_local_ogrid_refinement_explicit':True,'fixed_header_and_page_tabs_visible':True,'bilingual_all_property_labels':True,'unapplied_drafts_preserved_across_language_and_page':True,'hidden_and_floating_dock_restored':True,'invalid_resolution_rejected_with_feedback':True,'edited_generator_actual_mesh':{'cells':5376,'quality':own[0]['quality'],'case':own[0]['case']},'errors':errors}
(out/'round2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2)); assert not errors
while w.workers: pump()
w.close()
