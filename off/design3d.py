"""Actual polygonal extrusion of the project's geometry; never a claimed CFD mesh."""
import math
import vtk
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QHBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from .i18n import text

class Design3D(QWidget):
    selected=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent); box=QVBoxLayout(self); box.setContentsMargins(0,0,0,0); self.note=QLabel(); box.addWidget(self.note)
        self.widget=QVTKRenderWindowInteractor(self); box.addWidget(self.widget); self.renderer=vtk.vtkRenderer(); self.renderer.SetBackground(.94,.97,1); self.widget.GetRenderWindow().AddRenderer(self.renderer); self.widget.Initialize(); self.widget.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera()); self.actors=[]; self.press=None
        axes=vtk.vtkAxesActor(); self.axes=vtk.vtkOrientationMarkerWidget(); self.axes.SetOrientationMarker(axes); self.axes.SetInteractor(self.widget); self.axes.SetViewport(0,0,.17,.17); self.axes.EnabledOn(); self.axes.InteractiveOff()
        self.widget.AddObserver('LeftButtonPressEvent',lambda obj,event:setattr(self,'press',self.widget.GetEventPosition()))
        self.widget.AddObserver('LeftButtonReleaseEvent',self.pick)
        from .camera import controls
        row=QHBoxLayout(); controls(self,row); row.addStretch(); box.insertLayout(0,row)
    def actor(self,vertices,depth):
        points=vtk.vtkPoints()
        for x,y in vertices: points.InsertNextPoint(x,y,-depth/2)
        poly=vtk.vtkPolygon(); poly.GetPointIds().SetNumberOfIds(len(vertices))
        for i in range(len(vertices)): poly.GetPointIds().SetId(i,i)
        cells=vtk.vtkCellArray(); cells.InsertNextCell(poly); data=vtk.vtkPolyData(); data.SetPoints(points); data.SetPolys(cells)
        extrusion=vtk.vtkLinearExtrusionFilter(); extrusion.SetInputData(data); extrusion.SetExtrusionTypeToVectorExtrusion(); extrusion.SetVector(0,0,1); extrusion.SetScaleFactor(depth); extrusion.CappingOn(); extrusion.Update()
        normals=vtk.vtkPolyDataNormals(); normals.SetInputConnection(extrusion.GetOutputPort()); normals.ConsistencyOn(); normals.Update()
        mapper=vtk.vtkPolyDataMapper(); mapper.SetInputData(normals.GetOutput()); actor=vtk.vtkActor(); actor.SetMapper(mapper); self.renderer.AddActor(actor); return actor
    def rebuild(self,p,fit=False):
        self.renderer.RemoveAllViewProps(); self.actors=[]
        def circle(x,y,a,b): return [(x+a*math.cos(2*math.pi*i/128),y+b*math.sin(2*math.pi*i/128)) for i in range(128)]
        if p.mesh_method=='Structured cylinder O-grid' and p.shapes:
            s=p.shapes[0]; outline=circle(s['x'],s['y'],p.outer_radius,p.outer_radius)
        else: outline=[(p.xmin,p.ymin),(p.xmax,p.ymin),(p.xmax,p.ymax),(p.xmin,p.ymax)]
        domain=self.actor(outline,p.depth); domain.PickableOff(); domain.GetProperty().SetRepresentationToWireframe(); domain.GetProperty().SetColor(.5,.63,.75); domain.GetProperty().SetOpacity(.22)
        for i,s in enumerate(p.shapes):
            x,y=s['x'],s['y']; a,b=s['width']/2,s['height']/2
            from .geometry import vertices
            v=circle(x,y,a,b) if s['kind']=='circle' else vertices(s)
            actor=self.actor(v,p.depth); actor.GetProperty().SetColor(.23,.52,.68); self.actors.append((actor,('shape',i)))
        self.note.setText(text(f'3D extrusion design · depth {p.depth:g} m · {p.spanwise} spanwise layers · click solid to select; drag to orbit; wheel to zoom. Geometry only, not a generated mesh.',f'三维拉伸设计 · 深度 {p.depth:g} m · 展向 {p.spanwise} 层 · 点击实体选择，拖动旋转，滚轮缩放。此处为设计几何，不是已生成网格。')); self.note.setWordWrap(True)
        if fit: self.fit()
        else: self.widget.GetRenderWindow().Render()
    def fit(self):
        cam=self.renderer.GetActiveCamera(); cam.SetPosition(1,-1,1); cam.SetFocalPoint(0,0,0); cam.SetViewUp(0,0,1); self.renderer.ResetCamera(); self.widget.GetRenderWindow().Render()
    def highlight(self,tags):
        for actor,tag in self.actors:
            actor.GetProperty().SetColor(*((1.,.55,.08) if tag in tags else (.23,.52,.68)))
        self.widget.GetRenderWindow().Render()
    def pick(self,obj,event):
        pos=self.widget.GetEventPosition()
        if self.press is None or math.dist(pos,self.press)>5: return
        picker=vtk.vtkPropPicker(); picker.Pick(pos[0],pos[1],0,self.renderer); actor=picker.GetActor(); tags=[tag for candidate,tag in self.actors if candidate==actor]; self.highlight(tags); self.selected.emit(tags)
    def finalize(self): self.renderer.RemoveAllViewProps(); self.widget.Finalize()
