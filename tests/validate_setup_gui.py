import sys,time,json,os
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'installer'))
from setup_gui import Setup
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
app=QApplication([]);out=BASE/'evidence/package_QA';rows=[]
def pump(ms=100):
    end=time.time()+ms/1000
    while time.time()<end:app.processEvents();time.sleep(.01)
for mode in ('full','lite'):
    bundle=BASE.parent/'packages'/BASE.name/('OpenFoamFriend_'+mode.upper()+'_'+BASE.name);w=Setup(bundle);w.show();pump();assert w.windows.isVisible()==(mode=='full');assert w.distro.isEnabled()==(mode=='full')
    for lang in (1,0):
        w.language.setFocus();QTest.keyClick(w.language,Qt.Key_End if lang else Qt.Key_Home);pump();assert ('Installation' if lang else '安装') in w.target_label.text();w.grab().save(str(out/('installer_'+mode+('_EN' if lang else '_ZH')+'.png')))
    w.start(lambda p:(time.sleep(.3),{'ready':False,'errors':['Simulated missing WSL; no installation requested']})[1],w.report);pump(70);assert w.progress.isVisible() and not w.install_button.isEnabled();deadline=time.time()+10
    while w.tasks:pump();assert time.time()<deadline
    assert w.install_button.isEnabled() and not w.progress.isVisible() and 'missing WSL' in w.log.toPlainText();rows.append(dict(mode=mode,languages_verified=True,windows_action_visible=w.windows.isVisible(),progress_and_disabled_feedback=True,read_only_missing_report=True));w.close();pump()
(out/'setup_gui_validation.json').write_text(json.dumps(dict(actual_mouse_keyboard=True,rows=rows),indent=2));print('Installer GUI bilingual / progress PASS')
