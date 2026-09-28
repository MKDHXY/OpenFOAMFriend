from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QComboBox,QPushButton,QSlider,QLabel,QCheckBox,QFileDialog,QToolButton,QMenu
from PySide6.QtCore import Qt,Signal,QTimer
import vtk, numpy as np
from vtk.util.numpy_support import numpy_to_vtk,vtk_to_numpy
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from .post import Result
from .i18n import tr,text

class Viewer(QWidget):
    info=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self.result=None; layout=QVBoxLayout(self); toolbar=QHBoxLayout()
        self.field=QComboBox(); self.field.addItems(['Mesh','p','U']); self.field.currentTextChanged.connect(self.render_field)
        self.field.setToolTip('p: m²/s²; u,v,w: m/s; vorticity: s⁻¹. Vorticity is a VTK gradient estimate; outer-cell values are not exact wall vorticity. / 涡量为 VTK 梯度估计，外边界单元值不是精确壁面涡量。')
        self.edges=QCheckBox('Edges'); self.edges.setChecked(True); self.edges.toggled.connect(self.render_field)
        reset=QPushButton('Fit'); reset.clicked.connect(self.fit); self.label=QLabel('Load a real .foam case')
        self.slice=QComboBox(); self.slice.addItems(['Full volume','XY mid-slice','XZ mid-slice','YZ mid-slice']); self.slice.currentTextChanged.connect(self.render_field)
        toolbar.addWidget(self.field); toolbar.addWidget(self.edges); toolbar.addWidget(self.slice); toolbar.addWidget(reset); toolbar.addWidget(self.label); toolbar.addStretch(); layout.addLayout(toolbar)
        self.widget=QVTKRenderWindowInteractor(self); layout.addWidget(self.widget)
        self.renderer=vtk.vtkRenderer(); self.renderer.SetBackground(.94,.97,1); self.widget.GetRenderWindow().AddRenderer(self.renderer)
        self.widget.GetRenderWindow().SetMultiSamples(0); self.widget.Initialize()
        self.widget.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
        from .camera import controls
        controls(self,toolbar)
        playback=QHBoxLayout(); self.play_button=QPushButton('Play / 播放'); self.play_button.setCheckable(True); self.play_button.toggled.connect(self.toggle_playback); playback.addWidget(self.play_button)
        previous=QPushButton('◀'); previous.clicked.connect(lambda:self.slider.setValue(max(0,self.slider.value()-1))); playback.addWidget(previous)
        following=QPushButton('▶'); following.clicked.connect(lambda:self.slider.setValue(min(self.slider.maximum(),self.slider.value()+1))); playback.addWidget(following)
        self.play_rate=QComboBox()
        for value in [.1,.25,.5,1.,2.,5.,10.,50.]: self.play_rate.addItem(f'{value:g}×',value)
        self.play_rate.setCurrentIndex(3); self.play_rate.currentIndexChanged.connect(self.schedule_frame); playback.addWidget(self.play_rate)
        self.loop=QCheckBox('Loop / 循环'); playback.addWidget(self.loop); playback.addWidget(QLabel('Saved physical time / 已保存物理时间')); playback.addStretch(); layout.addLayout(playback)
        self.play_timer=QTimer(self); self.play_timer.setSingleShot(True); self.play_timer.timeout.connect(self.next_frame)
        self.slider=QSlider(Qt.Horizontal); self.slider.valueChanged.connect(self.time_changed); layout.addWidget(self.slider)
        self.mapper=vtk.vtkDataSetMapper(); self.actor=vtk.vtkActor(); self.actor.SetMapper(self.mapper); self.actor.SetVisibility(False); self.renderer.AddActor(self.actor)
        self.bar=vtk.vtkScalarBarActor(); self.bar.SetLookupTable(self.mapper.GetLookupTable()); self.bar.SetWidth(.12); self.bar.SetHeight(.65); self.bar.SetPosition(.87,.15); self.bar.GetTitleTextProperty().SetColor(.1,.2,.3); self.bar.GetLabelTextProperty().SetColor(.1,.2,.3)
        self.renderer.AddActor2D(self.bar); self.bar.SetVisibility(False)
        self.bar.SetUnconstrainedFontSize(True); self.bar.SetNumberOfLabels(5); self.bar.SetLabelFormat('%.3g')
        self.bar.GetTitleTextProperty().SetFontSize(16); self.bar.GetTitleTextProperty().BoldOff(); self.bar.GetTitleTextProperty().ItalicOff(); self.bar.GetLabelTextProperty().SetFontSize(12); self.bar.GetLabelTextProperty().BoldOff(); self.bar.GetLabelTextProperty().ItalicOff()
        self.mapper.GetLookupTable().SetHueRange(.667,0); self.mapper.GetLookupTable().Build()
        axes=vtk.vtkAxesActor(); self.orientation=vtk.vtkOrientationMarkerWidget(); self.orientation.SetOrientationMarker(axes); self.orientation.SetInteractor(self.widget); self.orientation.SetViewport(0,0,.18,.18); self.orientation.EnabledOn(); self.orientation.InteractiveOff()
        self.widget.AddObserver('LeftButtonPressEvent',self.pick)
        self.colour_settings={}; self.colour_key=''; self.colour_range=(0.,1.)
        self.colour_button=QToolButton(); self.colour_button.setText(text('Colour map…','色标设置…')); self.colour_button.setToolTip(text('Palette, fixed limits, ticks, title, size and position','配色、固定范围、刻度、标题、大小与位置')); self.colour_button.clicked.connect(self.edit_colour_map); self.colour_button.setEnabled(False); toolbar.insertWidget(3,self.colour_button)
        self.widget.setContextMenuPolicy(Qt.CustomContextMenu); self.widget.customContextMenuRequested.connect(self.scene_menu)
        self.retranslate()
    def load(self,path):
        self.set_result(Result(path))
    def set_result(self,result):
        self.play_button.setChecked(False); self.result=result; self.slider.blockSignals(True); self.slider.setRange(0,len(self.result.times)-1); self.slider.setValue(0); self.slider.blockSignals(False)
        self.field.blockSignals(True); self.field.clear()
        for name in ['Mesh']+self.result.arrays(): self.field.addItem(tr(name),name)
        self.field.blockSignals(False); self.render_field(); self.fit()
    def toggle_playback(self,playing):
        if playing and (not self.result or len(self.result.times)<2): self.play_button.setChecked(False); self.info.emit('Load at least two genuine frames / 至少加载两帧真实数据'); return
        self.play_button.setText('Pause / 暂停' if playing else 'Play / 播放'); self.schedule_frame()
    def schedule_frame(self,*args):
        self.play_timer.stop()
        if not self.play_button.isChecked() or not self.result: return
        index=self.slider.value()
        if index==len(self.result.times)-1:
            if not self.loop.isChecked(): self.play_button.setChecked(False); return
            self.slider.setValue(0); index=0
        dt=self.result.times[index+1]-self.result.times[index]; self.play_timer.start(max(10,round(1000*dt/self.play_rate.currentData())))
    def next_frame(self):
        if self.result: self.slider.setValue(min(self.slider.maximum(),self.slider.value()+1))
    def retranslate(self):
        self.colour_button.setText(text('Colour map…','色标设置…'))
        for combo,values in ((self.slice,['Full volume','XY mid-slice','XZ mid-slice','YZ mid-slice']),(self.field,['Mesh']+(self.result.arrays() if self.result else ['p','U']))):
            current=combo.currentData() or combo.currentText(); combo.blockSignals(True); combo.clear()
            for value in values: combo.addItem(tr(value),value)
            combo.setCurrentIndex(max(0,combo.findData(current))); combo.blockSignals(False)
        if self.result: self.render_field()
        else: self.label.setText(tr('Load a real .foam case'))
    def time_changed(self,index):
        if self.result: self.result.select(index); self.render_field(); self.schedule_frame()
    def render_field(self,*args):
        if not self.result: return
        self.actor.SetVisibility(True)
        if hasattr(self,'marker'): self.renderer.RemoveActor(self.marker)
        self.mapper.SetInputData(self.result.internal); name=self.field.currentData() or self.field.currentText()
        plane_name=self.slice.currentData() or self.slice.currentText()
        if plane_name in ('XY mid-slice','XZ mid-slice','YZ mid-slice'):
            plane=vtk.vtkPlane(); plane.SetOrigin(self.result.internal.GetCenter()); plane.SetNormal(*{'XY mid-slice':(0,0,1),'XZ mid-slice':(0,1,0),'YZ mid-slice':(1,0,0)}[plane_name]); cutter=vtk.vtkCutter(); cutter.GenerateTrianglesOff(); cutter.SetCutFunction(plane); cutter.SetInputData(self.result.internal); cutter.Update(); self.mapper.SetInputData(cutter.GetOutput())
        if name=='Mesh': self.mapper.ScalarVisibilityOff(); self.bar.SetVisibility(False); self.actor.GetProperty().SetColor(.53,.68,.8); self.colour_key=''; self.colour_button.setEnabled(False)
        else:
            array=self.result.internal.GetCellData().GetArray(name)
            if array:
                self.mapper.ScalarVisibilityOn(); self.mapper.SetScalarModeToUseCellFieldData(); self.mapper.SelectColorArray(name); self.colour_key=name; self.colour_range=array.GetRange(-1); self.colour_button.setEnabled(True); self.apply_colour_map(render=False)
        self.actor.GetProperty().SetEdgeVisibility(self.edges.isChecked()); self.actor.GetProperty().SetEdgeColor(.12,.25,.36)
        self.label.setText(f't = {self.result.times[self.result.index]:g} s | {self.result.internal.GetNumberOfCells():,} '+text('cells','单元')); self.widget.GetRenderWindow().Render()
    def fit(self): self.renderer.ResetCamera(); self.widget.GetRenderWindow().Render()
    def apply_colour_map(self,render=True):
        if not self.colour_key: return
        from .colourmap import settings_for,apply_lookup
        settings=self.colour_settings.setdefault(self.colour_key,settings_for(self.colour_key)); self.effective_colour_range=apply_lookup(self.mapper,self.bar,settings,self.colour_range,self.colour_key)
        if render: self.widget.GetRenderWindow().Render()
    def edit_colour_map(self):
        if not self.colour_key: return
        from .colourmap import ColourMapDialog
        self.play_button.setChecked(False); ColourMapDialog(self,self).exec()
    def scene_menu(self,pos):
        menu=QMenu(self); action=menu.addAction(text('Colour map & legend…','配色与色标…'),self.edit_colour_map); action.setEnabled(bool(self.colour_key)); menu.addAction(text('Fit view','适配视图'),self.fit); menu.exec(self.widget.mapToGlobal(pos))
    def pick(self,obj,event):
        pos=self.widget.GetEventPosition(); picker=vtk.vtkCellPicker(); picker.SetTolerance(.001)
        if picker.Pick(pos[0],pos[1],0,self.renderer): self.info.emit(f'Cell {picker.GetCellId()} | XYZ {picker.GetPickPosition()}')
    def show_quality(self,audit,metric='skewness'):
        self.play_button.setChecked(False)
        result,points,faces,centres,skew,angles=audit
        data=vtk.vtkPolyData(); pts=vtk.vtkPoints(); pts.SetData(numpy_to_vtk(points,deep=True)); data.SetPoints(pts)
        cells=vtk.vtkCellArray()
        for face in faces:
            cells.InsertNextCell(len(face))
            for v in face: cells.InsertCellPoint(int(v))
        data.SetPolys(cells); array=numpy_to_vtk(skew if metric=='skewness' else angles,deep=True); array.SetName(metric); data.GetCellData().SetScalars(array)
        self.mapper.SetInputData(data); self.actor.SetVisibility(True); self.mapper.SetScalarModeToUseCellData(); self.mapper.ScalarVisibilityOn(); self.mapper.SetScalarRange(array.GetRange()); self.actor.GetProperty().SetEdgeVisibility(True)
        self.colour_key=metric; self.colour_range=array.GetRange(); self.colour_button.setEnabled(True); self.apply_colour_map(render=False)
        worst=result['worst_skew_xyz' if metric=='skewness' else 'worst_nonortho_xyz']
        if hasattr(self,'marker'): self.renderer.RemoveActor(self.marker)
        sphere=vtk.vtkSphereSource(); sphere.SetCenter(*worst); sphere.SetRadius(max(np.ptp(points,axis=0))*.009); sphere.Update()
        mapper=vtk.vtkPolyDataMapper(); mapper.SetInputConnection(sphere.GetOutputPort()); self.marker=vtk.vtkActor(); self.marker.SetMapper(mapper); self.marker.GetProperty().SetColor(1,.12,.06); self.renderer.AddActor(self.marker)
        self.label.setText(f'Worst {metric} face at '+', '.join(f'{x:.5g}' for x in worst)); self.fit()
    def image(self):
        from PIL import Image
        grab=vtk.vtkWindowToImageFilter(); grab.SetInput(self.widget.GetRenderWindow()); grab.ReadFrontBufferOff(); grab.Update(); image=grab.GetOutput(); w,h,_=image.GetDimensions()
        return Image.fromarray(vtk_to_numpy(image.GetPointData().GetScalars()).reshape(h,w,-1)[::-1].copy())
    def gif(self,path):
        if not self.result: raise ValueError('Load a case first.')
        self.play_button.setChecked(False)
        old=self.result.index; frames=[]
        for i in range(len(self.result.times)):
            self.time_changed(i); frames.append(self.image())
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QEventLoop
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        frames[0].save(path,save_all=True,append_images=frames[1:],duration=150,loop=0); self.time_changed(old)
