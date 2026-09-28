"""Toolbar command stays checked in its actual dialog, then releases."""
import os,sys,json,time
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import Qt,QTimer
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.backend import BASE
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append
while w.workers: QTest.qWait(50)
action=next(a for a in w.geometry_toolbar.actions() if a.property('off_original')=='Design parameters / mesh code'); button=w.geometry_toolbar.widgetForAction(action); proof={}
def during():
    dialog=QApplication.activeModalWidget(); assert isinstance(dialog,QDialog); assert action.isChecked() and button.isChecked(); proof['actual_dialog_active']=True
    w.geometry_toolbar.grab().save(str(BASE/'evidence/button_command_active.png')); dialog.reject()
QTimer.singleShot(250,during); QTest.mouseClick(button,Qt.LeftButton); assert proof and not action.isChecked() and not button.isChecked()
line=w.tool_actions['line']; select=w.tool_actions['select']; QTest.mouseClick(w.sketch_toolbar.widgetForAction(line),Qt.LeftButton); assert line.isChecked() and not select.isChecked() and w.canvas.tool=='line'; w.sketch_toolbar.grab().save(str(BASE/'evidence/button_tool_selected.png')); QTest.mouseClick(w.sketch_toolbar.widgetForAction(select),Qt.LeftButton); assert select.isChecked() and not line.isChecked()
original=w.design_code; w.design_code=lambda:None
# Check the same command wrapper holds a disabled checked button until its worker finishes.
w.invoke_command(action,lambda:w.task(lambda:time.sleep(.3),lambda _:None)); assert action.isChecked() and not action.isEnabled(); w.context_update(); assert not action.isEnabled()
while w.workers: QTest.qWait(30)
assert not action.isChecked() and action.isEnabled()
report={'command_checked_while_real_dialog_open':True,'command_released_after_dialog':True,'exclusive_persistent_drawing_mode':True,'worker_checked_disabled_until_finish':True,'pending_not_reenabled_by_context_refresh':True,'errors':errors}; assert not errors
(BASE/'evidence/button_feedback_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2)); w.close()
