import sys,os,json,math,time
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt,QPointF
from off.gui import MainWindow
from off.backend import BASE,wsl
from off.models import Project
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append; QTest.qWait(400); c=w.canvas; out=BASE/'evidence'; out.mkdir(exist_ok=True)
def pixel(x,y): return c.mapFromScene(x*50,-y*50)
c.snap=0; c.add_curve([[2,2],[4,2]]); c.set_tool('line')
assert c.point(pixel(2,2))==(2,2); assert c.snap_label=='Endpoint'
assert c.point(pixel(3,2))==(3,2); assert c.snap_label=='Midpoint'
assert c.point(pixel(0,0))==(0,0)
c.start=(2,2); assert c.point(pixel(4,3),Qt.ShiftModifier)[1]==2; c.cancel_draft()
c.set_tool('circle'); QTest.mousePress(c.viewport(),Qt.LeftButton,pos=pixel(2,-2)); QTest.mouseMove(c.viewport(),pixel(3,-2)); QTest.mouseRelease(c.viewport(),Qt.LeftButton,pos=pixel(3,-2)); s=w.project.shapes[-1]; assert abs(s['x']-2)<.04 and abs(s['y']+2)<.04 and abs(s['width']-2)<.08
c.undo(); c.set_tool('polyline')
for x,y in [(2,-2),(3,-2),(3,-3)]: QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=pixel(x,y))
assert len(c.poly_points)==3; QTest.keyClick(c,Qt.Key_Backspace); assert len(c.poly_points)==2; QTest.keyClick(c,Qt.Key_Escape); assert not c.poly_points and c.tool=='polyline'; assert w.tool_actions['polyline'].isChecked(); QTest.keyClick(c,Qt.Key_Escape); assert c.tool=='select' and w.tool_actions['select'].isChecked()
QTest.keyClick(c,Qt.Key_L); assert c.tool=='line' and w.tool_actions['line'].isChecked(); before=c.object_snap; QTest.keyClick(c,Qt.Key_F3); assert c.object_snap!=before and w.snap_actions['object_snap'].isChecked()==c.object_snap
QTest.keyClick(c,Qt.Key_F8); assert c.ortho and w.snap_actions['ortho'].isChecked(); QTest.keyClick(c,Qt.Key_F9); assert not c.grid_snap
c.set_tool('rectangle'); QTest.mousePress(c.viewport(),Qt.LeftButton,pos=pixel(2,-2)); QTest.mouseMove(c.viewport(),pixel(4,-4)); preview=c.preview; QTest.mouseMove(c.viewport(),pixel(5,-4)); assert c.preview is preview; QTest.keyClick(c,Qt.Key_Escape); assert c.preview is None
previous=c.tool; QTest.mousePress(c.viewport(),Qt.MiddleButton,pos=pixel(2,2)); QTest.mouseMove(c.viewport(),pixel(1,1)); QTest.mouseRelease(c.viewport(),Qt.MiddleButton,pos=pixel(1,1)); assert c.pan_last is None and c.tool==previous
c.set_tool('select'); c.fit(); before=len(c.history); QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=pixel(7,7)); assert len(c.history)==before
c.set_tool('line'); QTest.mousePress(c.viewport(),Qt.LeftButton,pos=pixel(2,2))
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import QEvent
target=QPointF(pixel(4,3)); event=QMouseEvent(QEvent.MouseMove,target,target,QPointF(c.viewport().mapToGlobal(target.toPoint())),Qt.NoButton,Qt.LeftButton,Qt.NoModifier); QApplication.sendEvent(c.viewport(),event); assert c.preview is not None; assert c.hover[1]==c.start[1]; QTest.qWait(100); w.grab().save(str(out/'hci_EN.png')); c.cancel_draft(); w.change_language('zh'); assert w.snap_actions['ortho'].text()=='正交 F8'; w.grab().save(str(out/'hci_ZH.png')); w.change_language('en')
# Existing remote issue: validate environment with errexit and pipefail, without nounset.
probe=wsl(w.profile,'set -eo pipefail; source /opt/openfoam14/etc/bashrc >/dev/null 2>&1; command -v foamRun'); assert probe.returncode==0,probe.stderr
report={'anchor_snap':True,'shift_ortho':True,'circle_centre_radius':True,'polyline_backspace_escape':True,'keyboard_toolbar_sync':True,'middle_pan_preserves_tool':True,'preview_item_reused':True,'selection_no_undo_pollution':True,'bilingual_controls':True,'OpenFOAM_environment_without_nounset':probe.stdout.strip(),'errors':errors}; assert not errors
(out/'hci_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
while w.workers: QTest.qWait(100)
w.close()
