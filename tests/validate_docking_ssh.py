"""Actual toolbar pointer drag and persistence; SSH UI lifecycle with fixture transport."""
import os,sys,json,time
from pathlib import Path
from dataclasses import asdict
os.environ['OFF_LANGUAGE']='en'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.backend import BASE,DATA
from off import i18n
import off.ssh_gui as ssh
from off.ssh_backend import Cluster
app=QApplication([]); out=BASE/'evidence'; out.mkdir(exist_ok=True)
settings=i18n.settings_path(); original=settings.read_bytes() if settings.exists() else None
records_path=DATA/'remote_jobs.json'; original_records=records_path.read_bytes() if records_path.exists() else None
def wait(w):
    deadline=time.time()+60
    while w.workers: QTest.qWait(50); assert time.time()<deadline
def drag(w,area):
    toolbar=w.stage_toolbar; start=toolbar.mapToGlobal(QPoint(5,toolbar.height()//2))
    target=w.mapToGlobal(QPoint(20,w.menuBar().height()+6 if area==Qt.TopToolBarArea else w.height()-w.statusBar().height()-6))
    def event(kind,global_pos,button,buttons):
        local=toolbar.mapFromGlobal(global_pos)
        QApplication.sendEvent(toolbar,QMouseEvent(kind,QPointF(local),QPointF(global_pos),button,buttons,Qt.NoModifier))
        QTest.qWait(40)
    event(QEvent.MouseButtonPress,start,Qt.LeftButton,Qt.LeftButton)
    for i in range(1,16): event(QEvent.MouseMove,start+(target-start)*i/15,Qt.NoButton,Qt.LeftButton)
    event(QEvent.MouseButtonRelease,target,Qt.LeftButton,Qt.NoButton)
    assert w.toolBarArea(toolbar)==area,(w.toolBarArea(toolbar),area)
try:
    i18n.save_preference('workspace_tab_area','bottom'); w=MainWindow(); w.show(); w.timer.stop(); wait(w); QTest.qWait(150)
    assert w.toolBarArea(w.stage_toolbar)==Qt.BottomToolBarArea
    assert w.stage_toolbar.isMovable() and not w.stage_toolbar.isFloatable()
    assert not w.stage_toolbar.isAreaAllowed(Qt.LeftToolBarArea)
    w.grab().save(str(out/'tabs_default_bottom_EN.png'))
    drag(w,Qt.TopToolBarArea); w.grab().save(str(out/'tabs_dragged_top_EN.png')); w.close()
    w=MainWindow(); w.show(); w.timer.stop(); wait(w); QTest.qWait(200)
    assert w.toolBarArea(w.stage_toolbar)==Qt.TopToolBarArea
    drag(w,Qt.BottomToolBarArea); w.reset_layout(); assert w.toolBarArea(w.stage_toolbar)==Qt.BottomToolBarArea
    count=len(w.engine.store.all()); w.ssh_settings(); d=w.ssh_dialog; QTest.qWait(100)
    assert 'Configuration sequence' in d.help.toPlainText()
    d.grab().save(str(out/'ssh_configuration_EN.png'))
    config=Cluster(host='fixture-host',user='researcher',remote_root='/scratch/researcher/off',poll_seconds=30)
    d.records=[{'job_id':'12345','cluster':asdict(config),'remote_case':'/scratch/researcher/off/test','state':'SUBMITTED'}]
    calls=[]
    def fixture_query(c,ids):
        calls.append((c.host,ids)); return '12345|RUNNING|00:01|01:00:00|node01\n'
    ssh.query=fixture_query; d.timer.start(50); d.close(); assert not d.isVisible() and d.timer.isActive()
    deadline=time.time()+3
    while not calls or d.pending or getattr(d,'worker',None) is not None: QTest.qWait(30); assert time.time()<deadline
    d.timer.stop(); assert d.records[0]['state']=='RUNNING' and d.records[0]['elapsed']=='00:01'
    assert d.table.item(0,4).text()=='00:01'
    w.ssh_settings(); assert w.ssh_dialog is d and d.isVisible()
    # A saved record restarts the timer on dialog construction; no SSH network call is made here.
    d.persist(); recovered=ssh.SSHDialog(w); assert recovered.records[0]['job_id']=='12345' and recovered.timer.isActive(); recovered.timer.stop()
    assert len(w.engine.store.all())==count
    d.hide(); w.change_language('zh'); w.stage_nav.refresh(); w.grab().save(str(out/'tabs_default_bottom_ZH.png'))
    wait(w); w.close()
    result={'default_bottom':True,'actual_pointer_drag_top_and_bottom':True,'restart_position_retained':True,'reset_returns_bottom':True,'ssh_configuration_help':True,'hidden_dialog_polling':True,'reopened_dialog_reused':True,'persisted_job_polling_resumed':True,'elapsed_scheduler_details':True,'no_accidental_submission':True,'ssh_transport_test':'fixture only; no real cluster contacted','errors':[]}
    (out/'docking_ssh_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result,indent=2))
finally:
    if original is None: settings.unlink(missing_ok=True)
    else: settings.write_bytes(original)
    if original_records is None: records_path.unlink(missing_ok=True)
    else: records_path.write_bytes(original_records)
