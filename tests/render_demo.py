"""In-process Qt/VTK rendering test: captures our own application widgets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.backend import BASE

app=QApplication([]); window=MainWindow(); window.show(); QTest.qWait(800)
out=BASE/'evidence'; out.mkdir(exist_ok=True)
window.grab().save(str(out/'design.png'))
window.tabs.setCurrentIndex(2); QTest.qWait(500); window.grab().save(str(out/'queue.png'))
case=Path(r'\\wsl.localhost\Ubuntu\home\gongx\OpenFOAM\gongx14\run\OFF_validation_1b_20260926')
window.viewer.load(case/'OFF_validation_1b_20260926.foam'); window.tabs.setCurrentIndex(1); window.viewer.field.setCurrentText('p'); window.viewer.time_changed(5); QTest.qWait(500)
window.grab().save(str(out/'results.png')); window.viewer.image().save(out/'vtk.png')
window.viewer.gif(str(out/'animation.gif')); print(out)
window.timer.stop()
while window.workers: QTest.qWait(100)
window.close()
