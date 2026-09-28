import copy
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLineEdit,QComboBox,QLabel,QDialogButtonBox,QDoubleSpinBox,QSpinBox,QMessageBox
from .i18n import text

class DomainDialog(QDialog):
    def __init__(self,p,parent=None):
        super().__init__(parent); self.source=copy.deepcopy(p); self.setWindowTitle(text('2D / 3D model and domain','二维 / 三维模型与流场')); box=QVBoxLayout(self); form=QFormLayout(); box.addLayout(form); self.inputs={}
        self.dimension=QComboBox(); self.dimension.addItem(text('2D · one empty spanwise layer','二维 · 一层展向 empty'),2); self.dimension.addItem(text('3D · extruded volume mesh','三维 · 拉伸体网格'),3); self.dimension.setCurrentIndex(self.dimension.findData(p.dimension)); form.addRow(text('Simulation dimension','仿真维度'),self.dimension)
        for key,en,zh in [('name','Case name','算例名'),('xmin','X minimum / m','X 最小值 / m'),('xmax','X maximum / m','X 最大值 / m'),('ymin','Y minimum / m','Y 最小值 / m'),('ymax','Y maximum / m','Y 最大值 / m'),('depth','Z depth / m','Z 方向深度 / m'),('spanwise','Spanwise layers','展向层数')]:
            value=getattr(p,key); w=QLineEdit(value) if key=='name' else QSpinBox() if key=='spanwise' else QDoubleSpinBox()
            if key=='spanwise': w.setRange(1,2000); w.setValue(value)
            elif key!='name': w.setDecimals(12); w.setRange(1e-10 if key=='depth' else -1e9,1e9); w.setValue(value)
            form.addRow(text(en,zh),w); self.inputs[key]=w
        self.note=QLabel(text('Sketch the XY cross-section, then extrude through Z for a 3D model. Circle → cylinder; rectangle → prism; triangle → triangular prism. O-grid outer domain is circular and uses outer_radius. Arbitrary 3D CAD/booleans are not implemented.','绘制 XY 截面，沿 Z 拉伸形成三维模型：圆 → 圆柱，矩形 → 棱柱，三角形 → 三棱柱。O-grid 外流场为圆形，由 outer_radius 控制。尚未实现任意三维 CAD / 布尔建模。')); self.note.setWordWrap(True); box.addWidget(self.note)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); box.addWidget(buttons); self.dimension.currentIndexChanged.connect(self.update_dimension); self.update_dimension()
    def update_dimension(self):
        three=self.dimension.currentData()==3; self.inputs['spanwise'].setEnabled(three)
    def accept(self):
        p=copy.deepcopy(self.source); p.dimension=self.dimension.currentData()
        for key,w in self.inputs.items(): setattr(p,key,w.text() if key=='name' else w.value())
        if p.dimension==2: p.spanwise=1
        if p.dimension==2 and p.mesh_method=='Gmsh tetrahedral': QMessageBox.warning(self,self.windowTitle(),text('Tetrahedra require 3D. Change the mesh method before switching to 2D.','四面体要求三维，请先更换网格方法再切换到二维。')); return
        try: p.validate()
        except Exception as e: QMessageBox.warning(self,self.windowTitle(),str(e)); return
        self.result_project=p; super().accept()
