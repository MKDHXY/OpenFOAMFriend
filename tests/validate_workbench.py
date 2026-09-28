"""Real contextual UI + optional guide + evidence invalidation + guided solve."""
import sys,os,json,time,copy
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project
from off.backend import BASE
from off import i18n

app=QApplication([])
def ui_wait(ms):
    until=time.monotonic()+ms/1000
    while time.monotonic()<until: app.processEvents(); time.sleep(.01)
w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=lambda x:errors.append(x)
while w.workers: ui_wait(100)
w.pre_mode.setCurrentIndex(0); w.design_stack.setCurrentIndex(0); w.context_update(); w.jobs=w.engine.store.all(); w.set_guided(True); w.project=Project.load(BASE/'evidence'/'round1_project.off.json'); w.project.name='OFF_GUIDED_'+time.strftime('%Y%m%d_%H%M%S'); w.project.end_time=round(.06+.01*sum(j['name'].startswith('OFF_GUIDED_') for j in w.jobs),6); w.canvas.project=w.project; w.canvas.rebuild(); w.refresh_tree()
for page in (0,1,2,0):
    w.tabs.setCurrentIndex(page); ui_wait(50)
    assert w.sketch_toolbar.isVisible()==(page==0)
    assert w.geometry_toolbar.isVisible()==(page==0)
    assert w.scene_toolbar.isVisible()==(page==1)
    assert w.queue_toolbar.isVisible()==(page==2)
    assert all(a.isEnabled()==(page==0) for a in w.sketch_toolbar.actions() if a.isVisible()), [(a.text(),a.isEnabled(),a.isVisible()) for a in w.sketch_toolbar.actions()]
    assert not w.tool_actions['region'].isVisible() # refinement lives in Meshing, not a duplicate Design action
    assert all(not b.isVisible() for b,pages in w.context_buttons if page not in pages)
    assert w.sketch_settings_action.isEnabled()==(page==0)
    w.grab().save(str(BASE/'evidence'/f'context_page_{page}_EN.png'))
guide=w.guide; guide.choose(4); assert not guide.action.isEnabled(); assert not guide.next.isEnabled(); guide.execute(); assert not guide.matching(False)
guide.choose(0); guide.execute()
deadline=time.time()+30
while not guide.state()[0][0]:
    ui_wait(100)
    if errors: raise RuntimeError(errors)
    if time.time()>deadline: raise TimeoutError('Actual WSL probe')
guide.choose(1); guide.execute(); assert guide.state()[0][1]
guide.choose(2); assert w.pre_mode.currentIndex()==0;  assert guide.state()[0][2]; guide.execute()
while w.workers: ui_wait(50)
assert w.tabs.currentIndex()==1
guide.choose(3); guide.execute(); assert guide.state()[0][3]
# Stale mesh approvals do not survive parameter edits; changing flow retains mesh.
w.project.dictionary_overrides['system/blockMeshDict']='explicit changed topology'; guide.refresh(); assert not guide.state()[0][2]; w.project.dictionary_overrides.pop('system/blockMeshDict')
w.project.radial+=4; guide.refresh(); assert not guide.state()[0][2]; w.project.radial-=4
w.project.shapes[0]['width']*=1.1; guide.refresh(); assert not guide.state()[0][1] and not guide.state()[0][2]; w.project.shapes[0]['width']/=1.1
w.project.viscosity*=2; guide.refresh(); assert guide.state()[0][2] and not guide.state()[0][3]; w.project.viscosity/=2
guide.refresh(); assert all(guide.state()[0][:4]); guide.choose(4); assert guide.action.isEnabled(); guide.execute()
deadline=time.time()+120
while not guide.state()[0][5]:
    w.poll(); ui_wait(150)
    if errors: raise RuntimeError(errors)
    if time.time()>deadline: raise TimeoutError('Guided real solve')
guide.choose(5); guide.execute()
while w.workers: ui_wait(50)
assert w.viewer.result.internal.GetNumberOfCells()==5120; assert abs(w.viewer.result.times[-1]-w.project.end_time)<1e-9; assert all(a.isEnabled() for a in w.export_actions)
w.viewer.slice.setCurrentIndex(w.viewer.slice.findData('XY mid-slice')); w.viewer.fit(); w.grab().save(str(BASE/'evidence'/'guided_results_EN.png'))
w.set_guided(False); assert not w.guide_dock.isVisible(); assert i18n.preferences()['guided'] is False
w.change_language('zh'); assert i18n.preferences()['guided'] is False; w.set_guided(True); assert i18n.preferences()['language']=='zh'; guide.refresh(); w.grab().save(str(BASE/'evidence'/'guided_results_ZH.png')); w.tabs.setCurrentIndex(0); guide.choose(1); w.grab().save(str(BASE/'evidence'/'guided_geometry_ZH.png'))
w.inspector_dock.raise_(); ui_wait(100); assert w.guide_action.isChecked() and not w.guide_dock.isHidden(); w.guide_dock.raise_()
w.reset_layout(); assert w.sketch_toolbar.isVisible(); assert w.guide_dock.isVisible()
case=guide.state()[2]; report={'context_toolbars_passed':True,'drawing_actions_disabled_outside_geometry':True,'context_inspector_passed':True,'optional_guide_persisted_with_language':True,'actual_connection_probe':True,'geometry_and_physics_review':True,'mesh_evidence_invalidated_on_edit':True,'flow_edit_retains_mesh_but_invalidates_physics':True,'preparation_gate_blocks_submission':True,'guided_real_case':{'name':case['name'],'state':case['state'],'cores':case['project']['cores'],'cells':case['quality']['cells'],'end_time_s':case['time'],'saved_frames':len(w.viewer.result.times)},'errors':errors}
(BASE/'evidence'/'workbench_validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
while w.workers: ui_wait(100)
w.close()
