import os,sys,json,time
from pathlib import Path
os.environ['OFF_LANGUAGE']='zh';BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication,QToolButton
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project
from off import manual_topology as t
app=QApplication([]);w=MainWindow();w.show();w.timer.stop()
while w.workers:app.processEvents();time.sleep(.02)
e=BASE/'evidence/manual_topology';data=json.loads((e/'extended_validation.json').read_text());case=Path(data['meshes'][-1]['case']);w.project=Project.load(case/'off_project.json');w.canvas.project=w.project;w.refresh_tree();w.open_manual_topology();ed=w.manual_editor;ed.actions['select'][0].trigger();f=min(t.faces(ed.graph),key=lambda f:sum(x for x,y in f['poly'])/len(f['poly']))
for language,suffix in [('zh','ZH'),('en','EN')]:
 w.change_language(language);ed.select(('face',f['key']));ed.fit();QTest.qWait(150)
 for key,(action,*_) in ed.actions.items():
  b=next(b for b in ed.findChildren(QToolButton) if b.defaultAction() is action);assert b.width()>=b.fontMetrics().horizontalAdvance(action.text())+20,(key,b.width(),action.text())
 ed.grab().save(str(e/f'manual_regions_graded_{suffix}.png'))
(e/'final_layout_QA.json').write_text(json.dumps(dict(release=BASE.name,bilingual_complete_toolbar_text_widths=True,visible_property_scrollbars=True,errors=[]),indent=2));print('Native final layout PASS');w.close()
