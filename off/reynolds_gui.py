"""Compact native SI controls, explicit solve action and transactional result."""
from dataclasses import replace
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLabel,QComboBox,QPushButton,QHBoxLayout,QDialogButtonBox,QCheckBox
from .numeric_controls import ScientificSpin
from .i18n import text
from .reynolds import reference,reynolds,solve

class ReynoldsDialog(QDialog):
    def __init__(self,project,parent=None):
        super().__init__(parent); self.project=project; self.result_project=None
        self.setWindowTitle(text('Reynolds number & SI scaling','雷诺数与 SI 联动设置')); self.resize(610,450)
        box=QVBoxLayout(self); self.description=QLabel(text('Re = U L / nu · Incompressible Newtonian flow\nSolving Re changes only U or nu; it never resizes the geometry.','Re = U L / nu · 不可压缩牛顿流体\n按 Re 求解只改变 U 或 nu，不会缩放实体几何。')); self.description.setWordWrap(True); box.addWidget(self.description)
        form=QFormLayout(); box.addLayout(form); self.inputs={}
        try: length,source=reference(project)
        except ValueError: length,source=1.,'required'
        self.source=QComboBox(); self.source.addItem(text('From geometry','随几何自动更新'),'auto'); self.source.addItem(text('Custom reference L (not a geometry dimension)','自定义参考 L（不改变几何）'),'custom')
        self.source.setCurrentIndex(1 if project.reference_length>0 or source=='required' else 0); form.addRow(text('Reference length source','参考长度来源'),self.source)
        for key,label,value in [('velocity',text('U / m·s⁻¹','U / m·s⁻¹'),project.velocity),('length',text('L / m','L / m'),length),('viscosity',text('nu / m²·s⁻¹','nu / m²·s⁻¹'),project.viscosity),('target',text('Target Re / — (1–10⁷)','目标 Re / —（1–10⁷）'),min(1e7,max(1,reynolds(project.velocity,length,project.viscosity))))]:
            spin=ScientificSpin(); spin.setDecimals(24); spin.setRange(1e-20,1e12); spin.setValue(value); self.inputs[key]=spin; form.addRow(label,spin)
        self.inputs['target'].setRange(1,1e7)
        self.presets=QComboBox(); self.presets.addItem(text('Choose target Re…','选择目标 Re…'),None)
        for value in (1,10,40,100,200,1200,3900,10000,100000,1000000,10000000): self.presets.addItem(f'{value:,}',value)
        self.presets.currentIndexChanged.connect(self.preset); form.addRow(text('Common targets','常用目标'),self.presets)
        row=QHBoxLayout(); box.addLayout(row)
        for variable,label in [('viscosity',text('Calculate nu','计算 nu')),('velocity',text('Calculate U','计算 U'))]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,v=variable:self.calculate(v)); row.addWidget(b)
        self.reset_overrides=QCheckBox(text('Explicitly clear U / viscosity dictionary overrides when applying','应用时明确清除 U / 黏度字典覆盖')); self.reset_overrides.setChecked(False); self.reset_overrides.setVisible(any(k in project.dictionary_overrides for k in ('0/U','constant/physicalProperties'))); box.addWidget(self.reset_overrides)
        self.actual=QLabel(); self.actual.setWordWrap(True); box.addWidget(self.actual); self.error_label=QLabel(); self.error_label.setWordWrap(True); self.error_label.setStyleSheet('color:#a13125'); box.addWidget(self.error_label)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); box.addWidget(self.buttons)
        self.source.currentIndexChanged.connect(self.source_changed)
        for spin in self.inputs.values(): spin.valueChanged.connect(self.refresh)
        self.source_changed()
    def preset(self):
        if self.presets.currentData() is not None: self.inputs['target'].setValue(self.presets.currentData())
    def source_changed(self):
        auto=self.source.currentData()=='auto'; self.inputs['length'].setEnabled(not auto)
        if auto:
            try: self.inputs['length'].setValue(reference(replace(self.project,reference_length=0))[0])
            except ValueError as e: self.source.setCurrentIndex(1); self.error_label.setText(str(e))
        self.refresh()
    def refresh(self):
        v={k:s.value() for k,s in self.inputs.items()}; value=reynolds(v['velocity'],v['length'],v['viscosity'])
        self.actual.setText(text(f'Current Re = {value:.9g}\nU={v["velocity"]:.9g} m/s; L={v["length"]:.9g} m; nu={v["viscosity"]:.9g} m²/s\nTarget remains a request until Calculate U or Calculate nu is clicked.',f'当前 Re = {value:.9g}\nU={v["velocity"]:.9g} m/s；L={v["length"]:.9g} m；nu={v["viscosity"]:.9g} m²/s\n目标 Re 需点击“计算 U”或“计算 nu”才会落实。'))
    def calculate(self,variable):
        try:
            v={k:s.value() for k,s in self.inputs.items()}; self.inputs[variable].setValue(solve(v['target'],v['velocity'],v['length'],v['viscosity'],variable)); self.error_label.clear()
        except ValueError as e: self.error_label.setText(str(e))
    def accept(self):
        try:
            import copy
            result=copy.deepcopy(self.project); result.velocity=self.inputs['velocity'].value(); result.viscosity=self.inputs['viscosity'].value(); result.reference_length=self.inputs['length'].value() if self.source.currentData()=='custom' else 0.
            conflicts=[key for key in ('0/U','constant/physicalProperties') if key in result.dictionary_overrides]
            if conflicts and not self.reset_overrides.isChecked(): raise ValueError(text('Existing U / viscosity overrides may supersede these inputs. Review them or explicitly clear them below.','已有 U / 黏度覆盖可能替代界面参数。请核对，或明确勾选下方重置。'))
            if self.reset_overrides.isChecked(): result.dictionary_overrides={key:value for key,value in result.dictionary_overrides.items() if key not in conflicts}
            result.validate(); self.result_project=result
        except ValueError as e: self.error_label.setText(str(e)); return
        super().accept()
