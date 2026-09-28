"""Pointer selection and model/mesh dimension correspondence; additive features."""
import sys,os,json,time
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project
from off.domain_dialog import DomainDialog
from off.backend import BASE
from off.mesh import cylinder_dict
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append; out=BASE/'evidence'; out.mkdir(exist_ok=True)
while w.workers: QTest.qWait(50)
w.canvas.set_tool('select'); w.canvas.fit(); QTest.qWait(100); c=w.canvas
item=next(i for i in c.scene().items() if i.data(0)==('shape',0)); center=c.mapFromScene(item.boundingRect().center())
QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=center); assert item.isSelected()
c.scene().clearSelection(); label=next(i for i in c.scene().items() if i.data(1) is item); point=c.mapFromScene(label.sceneBoundingRect().center())
QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=point); assert item.isSelected(); assert 'shape 1' in w.selection_label.text()
before=len(c.history); w.retranslate(); assert any(i.isSelected() and i.data(0)==('shape',0) for i in c.scene().items()); assert len(c.history)==before
w.grab().save(str(out/'selection_XY_EN.png'))
domain=DomainDialog(w.project,w); domain.dimension.setCurrentIndex(domain.dimension.findData(2)); domain.accept(); assert domain.result_project.dimension==2 and domain.result_project.spanwise==1
p2=domain.result_project; assert 'type empty' in cylinder_dict(p2)
domain=DomainDialog(p2,w); domain.dimension.setCurrentIndex(domain.dimension.findData(3)); domain.inputs['depth'].setValue(2.5); domain.inputs['spanwise'].setValue(4); domain.accept(); p3=domain.result_project; assert p3.dimension==3 and 'type empty' not in cylinder_dict(p3)
w.project=p3; c.project=p3; c.rebuild(); w.refresh_tree(); w.design_view.setCurrentIndex(1); QTest.qWait(200)
actor=w.design3d.actors[0][0]; bounds=actor.GetBounds(); assert abs(bounds[4]+1.25)<1e-6 and abs(bounds[5]-1.25)<1e-6; assert actor.GetMapper().GetInput().GetNumberOfCells()>0
r=w.design3d.renderer; r.SetWorldPoint(.3535,-.3535,0,1); r.WorldToDisplay(); x,y,z=r.GetDisplayPoint(); widget=w.design3d.widget
QTest.mouseClick(widget,Qt.LeftButton,pos=QPoint(round(x),widget.height()-1-round(y))); QTest.qWait(100)
assert any(i.isSelected() and i.data(0)==('shape',0) for i in c.scene().items()),'3D pointer picking did not synchronize to sketch'
assert not w.sketch_toolbar.isVisible(); assert w.geometry_toolbar.isVisible()
from vtk.util.numpy_support import vtk_to_numpy
import vtk,numpy as np
from PIL import Image
grab=vtk.vtkWindowToImageFilter(); grab.SetInput(widget.GetRenderWindow()); grab.ReadFrontBufferOff(); grab.Update(); image=grab.GetOutput(); width,height,_=image.GetDimensions(); pixels=vtk_to_numpy(image.GetPointData().GetScalars()).reshape(height,width,-1)[::-1].copy(); assert pixels.std()>10; Image.fromarray(pixels).save(out/'design3D_geometry.png')
w.design_view.setCurrentIndex(0); assert w.sketch_toolbar.isVisible(); assert c.tool=='select'; w.change_language('zh'); w.grab().save(str(out/'dimension_controls_ZH.png'))
report={'pointer_object_selection':True,'pointer_label_selection':True,'selection_survives_language_refresh':True,'selection_no_undo_entry':True,'explicit_2D_3D_controls':True,'2D_one_empty_layer':True,'3D_volume_boundary':True,'actual_extrusion_bounds_m':list(bounds),'3D_pointer_pick_sync':True,'XY_drawing_preserved':True,'scope':'XY sketches extruded along Z; no arbitrary 3D CAD/booleans claimed','errors':errors}; assert not errors
(out/'selection_dimensions_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
while w.workers: QTest.qWait(50)
w.close()
