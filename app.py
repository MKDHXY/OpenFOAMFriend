import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from off.models import load_profile
from off.backend import Engine

def main():
    if '--worker' in sys.argv:
        engine=Engine(load_profile())
        while True:
            jobs=engine.tick()
            if all(j['state'] in ('DONE','FAILED','CANCELLED') for j in jobs): break
            time.sleep(engine.profile.poll_seconds)
        return
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from off.gui import MainWindow
    from off.backend import BASE
    app=QApplication(sys.argv); app.setApplicationName('Open Foam Friend'); app.setOrganizationName('zongxuan and hanwen')
    app.setWindowIcon(QIcon(str(BASE/'assets'/'icon.svg')))
    window=MainWindow(); window.show()
    from off.i18n import preferences
    from PySide6.QtCore import QTimer
    if preferences().get('show_welcome',True): QTimer.singleShot(600,window.welcome)
    sys.exit(app.exec())

if __name__=='__main__': main()
