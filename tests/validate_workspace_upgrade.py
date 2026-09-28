"""Actual pointer/WSL/VTK controls, analytic curl and serial case roundtrip."""
import sys,os,time,json
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import vtk,numpy as np
from vtk.util.numpy_support import numpy_to_vtk,vtk_to_numpy
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import Qt,QTimer,QProcess
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.backend import BASE
from off.post import derived_fields,Result
from off.workspace_tools import discover_wsl,Terminal,DesignCodeDialog,export_case
from off.dictionary_editor import format_foam
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append
while w.workers: QTest.qWait(50)
out=BASE/'evidence'; out.mkdir(exist_ok=True); c=w.canvas; c.fit(); c.set_tool('line'); before=len(w.project.curves)
a=c.mapFromScene(-200,-150); b=c.mapFromScene(200,-150)
QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=a); assert c.start is not None and len(w.project.curves)==before
QTest.mouseMove(c.viewport(),b); QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=b); assert c.start is None and len(w.project.curves)==before+1
c.undo(); assert len(w.project.curves)==before
QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=a); QTest.keyClick(c,Qt.Key_Escape); assert c.start is None
c.set_tool('line'); QTest.mousePress(c.viewport(),Qt.LeftButton,pos=a); QTest.mouseMove(c.viewport(),b); QTest.mouseRelease(c.viewport(),Qt.LeftButton,pos=b); assert len(w.project.curves)==before+1; c.undo()
key='div((nuEff*dev2(T(grad(U)))))'; code=format_foam('divSchemes { div(phi,U) Gauss linear; '+key+' Gauss linear; }'); assert key in code and 'div(phi,U)' in code
dialog=DesignCodeDialog(w.project,w); assert dialog.editor.toPlainText(); dialog.apply(); assert dialog.result_project is not None
w.task(lambda:time.sleep(.3),lambda _:None); assert w.activity.isVisible()
while w.workers: QTest.qWait(30)
assert not w.activity.isVisible()
def capture_welcome():
    dialog=QApplication.activeModalWidget(); assert isinstance(dialog,QDialog); dialog.grab().save(str(out/'welcome.png')); dialog.accept()
QTimer.singleShot(200,capture_welcome); w.welcome()
records=discover_wsl(); assert any(r.get('bashrcs') for r in records)
terminal=Terminal(w.profile); terminal.show(); terminal.start(); deadline=time.time()+40
while terminal.process.state()!=QProcess.Running:
    QTest.qWait(50)
    if time.time()>deadline: raise TimeoutError('WSL terminal startup')
terminal.command.setText("printf 'OFF_TERMINAL_PROOF:%s\\n' \"$WM_PROJECT_VERSION\"; pwd"); terminal.send()
while 'OFF_TERMINAL_PROOF:14' not in terminal.output.toPlainText():
    QTest.qWait(100)
    if time.time()>deadline: raise TimeoutError(terminal.output.toPlainText())
terminal.command.setText('exit'); terminal.send()
while terminal.process.state()!=QProcess.NotRunning: QTest.qWait(50)
terminal.close()
# Solid-body rotation U=(-2y,2x,0) has exact curl=(0,0,4).
image=vtk.vtkImageData(); image.SetDimensions(6,6,6); image.SetSpacing(.2,.2,.2)
append=vtk.vtkAppendFilter(); append.AddInputData(image); append.Update(); grid=vtk.vtkUnstructuredGrid(); grid.DeepCopy(append.GetOutput())
centres=vtk.vtkCellCenters(); centres.SetInputData(grid); centres.Update(); xyz=vtk_to_numpy(centres.GetOutput().GetPoints().GetData()); velocity=np.column_stack((-2*xyz[:,1],2*xyz[:,0],np.zeros(len(xyz))))
array=numpy_to_vtk(velocity,deep=True); array.SetName('U'); grid.GetCellData().AddArray(array); derived_fields(grid); curl=vtk_to_numpy(grid.GetCellData().GetArray('vorticity'))
interior=np.all((xyz>.39)&(xyz<.61),axis=1); assert interior.any()
analytic_error=float(np.max(np.abs(curl[interior]-np.array([0,0,4])))); boundary_error=float(np.max(np.abs(curl-np.array([0,0,4])))); assert analytic_error<1e-6,analytic_error
assert np.isfinite(curl).all() and np.all(curl[:,2]>0)
validation=json.loads((out/'validation.json').read_text()); source=Path(validation['rounds'][0]['case_folder']); target=out/('complete_foam_case_'+time.strftime('%H%M%S')); exported=export_case(next(source.glob('*.foam')),target); result=Result(exported['marker']); assert result.internal.GetNumberOfCells()==5120 and len(result.times)==6
w.viewer.set_result(result); w.tabs.setCurrentIndex(1); required={'u','v','w','p','speed','vorticity','vorticity_x','vorticity_y','vorticity_z','vorticity_magnitude'}; assert required<=set(result.arrays())
for name in required:
    w.viewer.field.setCurrentIndex(w.viewer.field.findData(name)); assert np.isfinite(vtk_to_numpy(result.internal.GetCellData().GetArray(name))).all()
w.viewer.play_rate.setCurrentIndex(w.viewer.play_rate.findData(.1)); w.viewer.play_button.setChecked(True); assert w.viewer.play_timer.isActive(); QTest.qWait(130); assert w.viewer.slider.value()>0; w.viewer.play_button.setChecked(False); paused=w.viewer.slider.value(); QTest.qWait(120); assert w.viewer.slider.value()==paused
for view in ('+X','-X','+Y','-Y','+Z','-Z','ISO'):
    w.viewer.view_orientation.setCurrentText(view); direction=w.viewer.renderer.GetActiveCamera().GetDirectionOfProjection(); assert all(np.isfinite(direction))
w.viewer.field.setCurrentIndex(w.viewer.field.findData('vorticity_z')); w.grab().save(str(out/'workspace_upgrade_EN.png')); w.change_language('zh'); w.grab().save(str(out/'workspace_upgrade_ZH.png'))
w.viewer.image().save(out/'workspace_vorticity_frame.png')
report={'welcome_page':True,'two_click_line':True,'drag_line_preserved':True,'cancel_undo':True,'parameter_code_editor':True,'foam_function_key_adjacency':True,'busy_indicator':True,'WSL_discovery':records,'actual_terminal_OpenFOAM14':True,'standard_views':True,'play_pause_rate':True,'real_fields':sorted(required),'analytic_curl_interior_max_abs_error':analytic_error,'analytic_curl_whole_domain_max_abs_error':boundary_error,'curl_limit':'Cell-gradient boundary reconstruction underestimates this constant curl at the outer cells; do not use boundary values as exact wall vorticity.','complete_case_export':exported,'reopened_export_cells':5120,'reopened_export_frames':len(result.times),'errors':errors}; assert not errors
(out/'workspace_upgrade_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2),flush=True)
while w.workers: QTest.qWait(50)
w.close()
