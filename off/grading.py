"""Explicit monotone spacing: ratio is final / first cell width."""
import math
from PySide6.QtWidgets import *
from .i18n import text

def cell_widths(length,count,ratio):
    if length<=0 or count<2 or ratio<=0: raise ValueError('Positive length and ratio; at least two cells.')
    q=ratio**(1/(count-1))
    weights=[q**i for i in range(count)]; total=sum(weights)
    return [length*w/total for w in weights]

def size_expression(region):
    if region['direction']=='uniform': return '1'
    axis=region['direction'][0]; key=axis; span=region['width' if key=='x' else 'height']; start=region[key]
    coord=f'(({axis}-{start})/{span})' if region['direction'].endswith('+') else f'(({start+span}-{axis})/{span})'
    clipped=f'(0.5*(Abs({coord})-Abs(({coord})-1)+1))'
    return f"{region['ratio']}^({clipped})"

class GradingDialog(QDialog):
    def __init__(self,project,parent=None):
        super().__init__(parent); self.project=project; self.setWindowTitle(text('Mesh spacing / monotone grading','网格间距 / 单调渐变')); self.resize(620,530); box=QVBoxLayout(self); form=QFormLayout(); box.addLayout(form)
        self.target=QComboBox(); self.target.addItem(text('O-grid radial direction','O 网格径向'),-1)
        for i,r in enumerate(project.regions): self.target.addItem(f'R{i+1}',i)
        self.mode=QComboBox(); self.mode.addItems([text('Uniform','均匀'),text('Increasing spacing','间距递增'),text('Decreasing spacing','间距递减')]); self.direction=QComboBox(); self.direction.addItems(['x+','x-','y+','y-'])
        self.ratio=QDoubleSpinBox(); self.ratio.setRange(1.000001,1000); self.ratio.setDecimals(6); self.ratio.setValue(4)
        self.size=QDoubleSpinBox(); self.size.setRange(.000000001,10000); self.size.setDecimals(9); self.size.setValue(project.cell_size/2)
        for label,widget in [(text('Target','目标'),self.target),(text('Distribution','分布'),self.mode),(text('Direction','方向'),self.direction),(text('Coarse / fine ratio','粗 / 细间距比'),self.ratio),(text('Region starting target size (m)','区域起始目标间距 (m)'),self.size)]: form.addRow(label,widget)
        self.preview=QPlainTextEdit(); self.preview.setReadOnly(True); box.addWidget(self.preview)
        box.addWidget(QLabel(text('O-grid: exact first/last widths; region: Gmsh target size or conformal block grading. Gmsh is capped by background size. Multiple box partitions restart grading per segment.','O 网格：精确首尾单元宽度；区域：Gmsh 目标尺寸或共形分块渐变。Gmsh 受背景尺寸上限限制；多个分块在每段重新渐变。')))
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); box.addWidget(buttons)
        self.target.currentIndexChanged.connect(self.load); self.mode.currentIndexChanged.connect(self.update); self.direction.currentIndexChanged.connect(self.update); self.ratio.valueChanged.connect(self.update); self.size.valueChanged.connect(self.update); self.load()
    def actual_ratio(self): return 1 if self.mode.currentIndex()==0 else self.ratio.value() if self.mode.currentIndex()==1 else 1/self.ratio.value()
    def load(self):
        i=self.target.currentData(); r=self.project.grading if i==-1 else self.project.regions[i]['ratio']; self.mode.setCurrentIndex(0 if abs(r-1)<1e-10 else 1 if r>1 else 2); self.ratio.setValue(max(r,1/r))
        self.direction.setEnabled(i!=-1); self.size.setEnabled(i!=-1)
        if i!=-1: self.direction.setCurrentText(self.project.regions[i]['direction'] if self.project.regions[i]['direction']!='uniform' else 'x+'); self.size.setValue(self.project.regions[i]['size'])
        self.update()
    def update(self,*args):
        i=self.target.currentData(); ratio=self.actual_ratio()
        if i==-1:
            length=self.project.outer_radius-self.project.shapes[0]['width']/2 if self.project.shapes else self.project.outer_radius; widths=cell_widths(length,self.project.radial,ratio)
            s=text('Radial: cylinder → far boundary','径向：圆柱 → 外边界')+f'\nN={len(widths)}; L={length:g} m\nh_last/h_first={ratio:g}\nq=ratio^(1/(N-1))={ratio**(1/(len(widths)-1)):g}\nh_first={widths[0]:.8g} m; h_last={widths[-1]:.8g} m\n'+', '.join(f'{w:.5g}' for w in widths)
        else: s=f'R{i+1} · {self.direction.currentText()}\nh_start={self.size.value():g} m; h_end={self.size.value()*ratio:g} m\nh(s)=h_start * (h_end/h_start)^s, 0<=s<=1\n'+text('The display gives targets; inspect the generated mesh to verify actual sizes.','显示值为目标间距；实际间距需检查生成网格。')
        self.preview.setPlainText(s)
    def apply(self):
        i=self.target.currentData(); ratio=self.actual_ratio()
        if i==-1: self.project.grading=ratio
        else: self.project.regions[i].update(size=self.size.value(),direction='uniform' if self.mode.currentIndex()==0 else self.direction.currentText(),ratio=ratio)
