import sys,json,os
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools'))
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project
from off.physics import MODELS
from cycle_ledger import record
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop()
while w.workers: QTest.qWait(20)
proof={}
def choose():
    d=app.activeModalWidget(); c=d.inputs['turbulence']; assert c.count()==24
    c.setCurrentIndex(c.findData('WALE')); assert any('LES/DES requires 3D' in l.text() for l in d.findChildren(QLabel))
    d.grab().save(str(BASE/'evidence/model_selector.png')); d.accept(); proof['all_options_visible']=True
QTimer.singleShot(150,choose); w.flow_settings(); assert w.project.turbulence=='WALE'
for dimension,span in [(2,1),(3,1)]:
    try: Project(turbulence='WALE',dimension=dimension,spanwise=span).validate(); raise AssertionError('invalid LES accepted')
    except ValueError: pass
Project(turbulence='kOmegaSST',dimension=2,spanwise=1).validate(); proof['twoD_RAS_retained']=True; proof['LES_volume_guard']=True; proof['errors']=[]
(BASE/'evidence/model_ui_validation.json').write_text(json.dumps(proof,indent=2)); record(5,'A flat model list has no scientific context and can submit a nominal LES on a 2D mesh.','Native model family labels, required-field explanation, explicit transient-RAS semantics and 3D LES/hybrid submission guards.','Select WALE in the real dialog; reject 2D/one-layer LES and retain 2D RAS.','model_ui_validation.json'); w.close(); print(proof)
