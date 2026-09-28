import sys,os,json
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from off.gui import MainWindow
from off.backend import BASE
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append; out=BASE/'evidence'; out.mkdir(exist_ok=True)
while w.workers: QTest.qWait(100)
nav=w.stage_nav; count=len(w.engine.store.all()); name=w.project.name
for index,page in enumerate(nav.pages):
    QTest.mouseClick(nav.bar,Qt.LeftButton,pos=nav.bar.tabRect(index).center()); QTest.qWait(80); assert w.tabs.currentIndex()==page; assert nav.bar.currentIndex()==index; assert nav.bar.isVisible() and w.tree_dock.isVisible(); assert not nav.header.isVisible(); assert w.sketch_toolbar.isVisible()==(page==0); w.canvas.fit(); w.grab().save(str(out/f'navigation_{page}_EN.png'))
assert w.stage_toolbar.height()<60; assert len(w.engine.store.all())==count and w.project.name==name
w.tree_dock.hide(); QTest.keyClick(w,Qt.Key_1,Qt.ControlModifier); assert w.tabs.currentIndex()==0 and nav.bar.currentIndex()==0
w.change_language('zh'); assert nav.bar.tabText(0)=='前处理'; w.tree_dock.show(); QTest.mouseClick(nav.bar,Qt.LeftButton,pos=nav.bar.tabRect(2).center()); assert w.tabs.currentIndex()==1; assert '后处理' in nav.context.text(); w.grab().save(str(out/'navigation_1_ZH.png'))
report={'conventional_compact_tabs':True,'tree_retained':True,'tabs_work_without_tree':True,'bilingual_labels':True,'stage_shortcuts':True,'no_accidental_submission':True,'drawing_tools_contextual':True,'large_cards_removed':True,'toolbar_height_px':w.stage_toolbar.height(),'errors':errors}; assert not errors; (out/'navigation_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
while w.workers: QTest.qWait(100)
w.close()
