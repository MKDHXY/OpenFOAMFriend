"""Axis-aligned, model-centred camera controls shared by both VTK scenes."""
from PySide6.QtWidgets import QComboBox,QCheckBox
VIEWS={'ISO':((1,-1,1),(0,0,1)),'+X':((1,0,0),(0,0,1)),'-X':((-1,0,0),(0,0,1)),'+Y':((0,1,0),(0,0,1)),'-Y':((0,-1,0),(0,0,1)),'+Z':((0,0,1),(0,1,0)),'-Z':((0,0,-1),(0,1,0))}
def align(renderer,widget,name='ISO',parallel=False):
    bounds=renderer.ComputeVisiblePropBounds()
    centre=[(bounds[2*i]+bounds[2*i+1])/2 for i in range(3)] if bounds[0]<=bounds[1] else [0,0,0]
    direction,up=VIEWS[name]; cam=renderer.GetActiveCamera(); cam.SetFocalPoint(*centre); cam.SetPosition(*(centre[i]+direction[i] for i in range(3))); cam.SetViewUp(*up); cam.SetParallelProjection(parallel); renderer.ResetCamera(); renderer.ResetCameraClippingRange(); widget.GetRenderWindow().Render()
def controls(owner,row):
    owner.view_orientation=QComboBox(); owner.view_orientation.addItems(VIEWS); owner.orthographic=QCheckBox('Orthographic / 正交投影'); row.addWidget(owner.view_orientation); row.addWidget(owner.orthographic)
    callback=lambda:align(owner.renderer,owner.widget,owner.view_orientation.currentText(),owner.orthographic.isChecked())
    owner.view_orientation.currentTextChanged.connect(callback); owner.orthographic.toggled.connect(callback)
