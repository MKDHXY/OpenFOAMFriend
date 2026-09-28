"""Baseline real mouse clicks. No handler calls or mocked routing."""
import sys,os,time,json
from pathlib import Path
os.environ['OFF_LANGUAGE']='zh'; BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,'D:/UoM/openfoamfriend/v20260928_023043')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from off.gui import MainWindow
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); deadline=time.time()+60
while w.workers:
    app.processEvents(); time.sleep(.02); assert time.time()<deadline
root=w.tree.topLevelItem(0); mesh=next(root.child(i) for i in range(root.childCount()) if root.child(i).data(0,Qt.UserRole)==('nav','mesh'))
rows=[]
for child in [mesh.child(0),mesh.child(1)]:
    w.tabs.setCurrentIndex(2); app.processEvents(); rect=w.tree.visualItemRect(child)
    QTest.mouseClick(w.tree.viewport(),Qt.LeftButton,pos=QPoint(rect.left()+60,rect.center().y())); app.processEvents()
    rows.append({'row':child.text(0),'user_role':child.data(0,Qt.UserRole),'stage_after_single_click':w.tabs.currentIndex(),'no_route':w.tabs.currentIndex()==2})
w.grab().save(str(BASE/'evidence/navigation_click_QA/baseline_dead_rows.png'))
assert all(r['no_route'] and r['user_role'] is None for r in rows)
(BASE/'evidence/navigation_click_QA/baseline.json').write_text(json.dumps({'source_release':'v20260928_023043','real_mouse_clicks':rows,'defect_confirmed':True},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False,indent=2)); w.close()
