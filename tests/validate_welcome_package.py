import sys,os,time,json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication,QComboBox,QPushButton
from PySide6.QtCore import Qt,QTimer
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off import i18n
app=QApplication([]);w=MainWindow();w.show();w.timer.stop();out=BASE/'evidence/package_QA';out.mkdir(parents=True,exist_ok=True)
deadline=time.time()+60
while w.workers:app.processEvents();time.sleep(.01);assert time.time()<deadline
original=w.project;rows=[];exceptions=[]
def interactions():
    try:
        dialog=app.activeModalWidget();assert dialog.objectName()=='welcomeProjects';combo=dialog.findChild(QComboBox,'welcomeLanguage');assert combo
        for language in ('en','zh'):
            combo.setFocus();QTest.keyClick(combo,Qt.Key_Home if language=='zh' else Qt.Key_End);app.processEvents()
            assert combo.currentData()==i18n.LANG==language
            button=dialog.findChild(QPushButton,'welcomeContinue');assert button.text()==('进入工作台' if language=='zh' else 'Continue workspace')
            dialog.grab().save(str(out/('welcome_'+language+'.png')));rows.append(dict(language=language,label=button.text(),main_language=i18n.LANG))
        QTest.mouseClick(button,Qt.LeftButton)
    except Exception as e:exceptions.append(str(e));dialog.reject()
QTimer.singleShot(200,interactions);w.welcome();assert not exceptions,exceptions;assert w.project is original
assert i18n.preferences()['language']=='zh';assert len(rows)==2
while w.workers:app.processEvents();time.sleep(.01)
w.close();(out/'welcome_validation.json').write_text(json.dumps(dict(release=BASE.name,actual_keyboard_and_mouse=True,project_preserved=True,language_persisted=True,rows=rows,errors=exceptions),indent=2),encoding='utf-8');print('Welcome bilingual PASS',flush=True)
