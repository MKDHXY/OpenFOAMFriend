"""Persistent mesh property pages reached by actual tree and toolbar clicks."""
import copy,json
from dataclasses import asdict
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QTabWidget,QComboBox,QSpinBox,QPushButton,QScrollArea
from .numeric_controls import ScientificSpin
from .grading import cell_widths
from .i18n import text,tr

METHODS=('Structured cylinder O-grid','Structured partitioned box','Gmsh triangle / prism','Gmsh quadrilateral / prism','Gmsh tetrahedral','Manual topology (blockMesh)','Manual topology (Gmsh)')

class MeshInspector(QWidget):
    def __init__(self,window):
        super().__init__(); self.window=window; self.loading=True; self.signature=None; self.setMinimumWidth(295)
        box=QVBoxLayout(self); self.heading=QLabel(); self.heading.setWordWrap(True); self.heading.setStyleSheet('font-weight:600;color:#155976'); box.addWidget(self.heading)
        self.pages=QTabWidget(); box.addWidget(self.pages,1); self.generator=QWidget(); self.refinement=QWidget()
        for body,title in [(self.generator,'Generator'),(self.refinement,'Refinement')]:
            scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(body); self.pages.addTab(scroll,title)
        gbox=QVBoxLayout(self.generator); form=QFormLayout(); form.setRowWrapPolicy(QFormLayout.WrapLongRows); gbox.addLayout(form); self.fields={}; self.labels={}
        keys=('mesh_method','radial','circumferential','spanwise','outer_radius','grading','cell_size','smoothing','nonortho_limit','skew_limit')
        for key in keys:
            if key=='mesh_method':
                widget=QComboBox()
                for method in METHODS: widget.addItem(method,method)
                widget.currentIndexChanged.connect(self.generator_relevance)
            elif key in ('radial','circumferential','spanwise','smoothing'):
                widget=QSpinBox(); widget.setRange(0 if key=='smoothing' else 1,1_000_000)
            else:
                widget=ScientificSpin(); widget.setRange(1e-12,1e9)
            self.fields[key]=widget; label=QLabel(); label.setWordWrap(True); self.labels[key]=label; form.addRow(label,widget)
        self.generator_note=QLabel(); self.generator_note.setWordWrap(True); gbox.addWidget(self.generator_note)
        self.apply_generator_button=QPushButton(); self.apply_generator_button.setObjectName('applyMeshGenerator'); self.apply_generator_button.clicked.connect(self.apply_generator); gbox.addWidget(self.apply_generator_button)
        self.manual_button=QPushButton(); self.manual_button.clicked.connect(window.open_manual_topology); gbox.addWidget(self.manual_button)
        self.advanced_generator=QPushButton(); self.advanced_generator.clicked.connect(window.mesh_settings_dialog); gbox.addWidget(self.advanced_generator); gbox.addStretch()
        rbox=QVBoxLayout(self.refinement); rform=QFormLayout(); rform.setRowWrapPolicy(QFormLayout.WrapLongRows); rbox.addLayout(rform); self.target=QComboBox(); self.target.setObjectName('refinementTarget'); self.refinement_labels=[]; self.region_labels={}
        def row(en,zh,widget):
            label=QLabel(); label.setWordWrap(True); self.refinement_labels.append((label,en,zh)); rform.addRow(label,widget); return label
        row('Target','目标',self.target)
        self.mode=QComboBox(); self.mode.addItems(['Uniform','Increasing spacing','Decreasing spacing']); row('Distribution','分布',self.mode)
        self.direction=QComboBox(); self.direction.addItems(['x+','x-','y+','y-']); self.direction_label=row('Direction','方向',self.direction)
        self.ratio=ScientificSpin(); self.ratio.setRange(1.000001,1000); row('Coarse / fine ratio','粗 / 细间距比',self.ratio)
        self.region_fields={}
        for key,en,zh in [('x','x start / m','x 起点 / m'),('y','y start / m','y 起点 / m'),('width','Width / m','宽度 / m'),('height','Height / m','高度 / m'),('size','Start size / m','起始间距 / m')]:
            widget=ScientificSpin(); widget.setRange(-1e9 if key in ('x','y') else 1e-12,1e9); self.region_fields[key]=widget; self.region_labels[key]=row(en,zh,widget)
        self.refinement_note=QLabel(); self.refinement_note.setWordWrap(True); rbox.addWidget(self.refinement_note)
        self.preview=QLabel(); self.preview.setWordWrap(True); self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse); self.preview.setStyleSheet('background:#e8f1f7;padding:8px;'); rbox.addWidget(self.preview)
        self.apply_refinement_button=QPushButton(); self.apply_refinement_button.setObjectName('applyMeshRefinement'); self.apply_refinement_button.clicked.connect(self.apply_refinement); rbox.addWidget(self.apply_refinement_button)
        self.draw_button=QPushButton(); self.draw_button.setObjectName('drawMeshRegion'); self.draw_button.clicked.connect(window.draw_refinement_region); rbox.addWidget(self.draw_button)
        self.advanced_spacing=QPushButton(); self.advanced_spacing.clicked.connect(window.spacing_dialog); rbox.addWidget(self.advanced_spacing); rbox.addStretch()
        self.target.currentIndexChanged.connect(self.load_target)
        for widget in (self.mode,self.direction): widget.currentIndexChanged.connect(self.update_preview)
        self.ratio.valueChanged.connect(self.update_preview)
        for widget in self.region_fields.values(): widget.valueChanged.connect(self.update_preview)
        self.feedback=QLabel(); self.feedback.setWordWrap(True); self.feedback.setObjectName('meshPropertyFeedback'); box.addWidget(self.feedback)
        self.loading=False; self.reload()

    def reload(self,page=None,target=None):
        p=self.window.project; signature=json.dumps(asdict(p),sort_keys=True); self.retranslate()
        if signature==self.signature:
            if page is not None: self.pages.setCurrentIndex(0 if page=='generator' else 1)
            if target is not None and target!=self.target.currentData(): self.target.setCurrentIndex(self.target.findData(target))
            if self.target.currentData()==-1: self.target.setItemText(self.target.currentIndex(),text('O-grid radial spacing','O 网格径向间距'))
            if self.target.currentData() is None: self.target.setItemText(self.target.currentIndex(),text('No regions — draw one','暂无区域 — 请先绘制'))
            self.generator_relevance(); self.update_preview(); return
        self.signature=signature; self.loading=True
        for key,widget in self.fields.items():
            if key=='mesh_method': widget.setCurrentIndex(widget.findData(p.mesh_method))
            else: widget.setValue(getattr(p,key))
        previous=self.target.currentData(); self.target.blockSignals(True); self.target.clear()
        if p.mesh_method=='Structured cylinder O-grid': self.target.addItem(text('O-grid radial spacing','O 网格径向间距'),-1)
        for i,r in enumerate(p.regions): self.target.addItem(f'R{i+1} · {r["direction"]} · h={r["size"]:g} m',i)
        if not self.target.count(): self.target.addItem(text('No regions — draw one','暂无区域 — 请先绘制'),None)
        index=self.target.findData(target if target is not None else previous)
        self.target.setCurrentIndex(max(0,index)); self.target.blockSignals(False); self.loading=False
        if page is not None: self.pages.setCurrentIndex(0 if page=='generator' else 1)
        self.generator_relevance(); self.load_target()

    def retranslate(self):
        self.manual_button.setText(text('Manual topology editor…','手动拓扑编辑器…')); self.heading.setText(text('Mesh properties — editable settings','网格属性 — 可编辑设置')); self.pages.setTabText(0,text('Generator','生成器')); self.pages.setTabText(1,text('Refinement / spacing','加密 / 间距'))
        labels={'mesh_method':('Mesh generator','网格生成器'),'radial':('Radial cells','径向单元数'),'circumferential':('Circumferential cells','圆周单元数'),'spanwise':('Spanwise cells','展向单元数'),'outer_radius':('Outer radius / m','外边界半径 / m'),'grading':('Radial h_last/h_first','径向末/首间距比'),'cell_size':('Background size / m','背景间距 / m'),'smoothing':('Smoothing iterations','平滑迭代数'),'nonortho_limit':('Max non-orthogonality / °','最大非正交阈值 / °'),'skew_limit':('Max skewness','最大偏斜阈值')}
        for key,(en,zh) in labels.items(): self.labels[key].setText(text(en,zh))
        for label,en,zh in self.refinement_labels: label.setText(text(en,zh))
        self.advanced_generator.setText(text('Full settings dialog…','完整设置窗口…')); self.advanced_spacing.setText(text('Full spacing dialog…','完整间距窗口…'))
        for i,method in enumerate(METHODS): self.fields['mesh_method'].setItemText(i,tr(method))
        for i,(en,zh) in enumerate([('Uniform','均匀'),('Increasing spacing','间距递增'),('Decreasing spacing','间距递减')]): self.mode.setItemText(i,text(en,zh))
        self.apply_generator_button.setText(text('Apply generator settings','应用生成器设置')); self.apply_refinement_button.setText(text('Apply spacing settings','应用间距设置')); self.draw_button.setText(text('Draw a refinement region','绘制加密区域'))

    def generator_relevance(self,*args):
        if self.loading: return
        p=self.window.project; method=self.fields['mesh_method'].currentData(); ogrid=method=='Structured cylinder O-grid'
        for key in ('radial','circumferential','outer_radius','grading'): self.fields[key].setEnabled(ogrid)
        self.fields['cell_size'].setEnabled(not ogrid); self.fields['smoothing'].setEnabled(method.startswith('Gmsh')); self.fields['spanwise'].setEnabled(p.dimension==3 and method!='Gmsh tetrahedral')
        manual='system/blockMeshDict' in p.dictionary_overrides
        self.generator_note.setText(text('Apply stores project inputs; Generate/check produces the actual grid. Manual blockMeshDict override is active and remains authoritative.' if manual else 'Apply stores project inputs; Generate/check produces the actual grid. Changing the backend is validated against the geometry.','应用保存项目输入；生成/检查才产生实际网格。当前手动 blockMeshDict 覆盖仍为实际输入。' if manual else '应用保存项目输入；生成/检查才产生实际网格。更换生成器会核验几何兼容性。'))

    def load_target(self,*args):
        if self.loading: return
        p=self.window.project; index=self.target.currentData(); self.loading=True
        if index==-1: ratio=p.grading
        elif index is not None:
            r=p.regions[index]; ratio=r['ratio']
            for key,widget in self.region_fields.items(): widget.setValue(r[key])
            self.direction.setCurrentText('x+' if r['direction']=='uniform' else r['direction'])
        else: ratio=1
        self.mode.setCurrentIndex(0 if abs(ratio-1)<1e-10 else 1 if ratio>1 else 2); self.ratio.setValue(max(ratio,1/ratio)); self.loading=False; self.update_preview()

    def actual_ratio(self): return 1 if self.mode.currentIndex()==0 else self.ratio.value() if self.mode.currentIndex()==1 else 1/self.ratio.value()

    def update_preview(self,*args):
        if self.loading: return
        p=self.window.project; index=self.target.currentData(); ratio=self.actual_ratio(); local=index is not None and index>=0; unsupported=local and (p.mesh_method=='Structured cylinder O-grid' or p.mesh_method.startswith('Manual topology'))
        for key,widget in self.region_fields.items():
            widget.setEnabled(local); widget.setVisible(local); self.region_labels[key].setVisible(local)
        self.direction.setVisible(local); self.direction_label.setVisible(local)
        self.mode.setEnabled(index is not None); self.ratio.setEnabled(index is not None and self.mode.currentIndex()!=0); self.direction.setEnabled(local and self.mode.currentIndex()!=0)
        self.apply_refinement_button.setEnabled(index is not None and not unsupported)
        if index==-1:
            length=p.outer_radius-p.shapes[0]['width']/2; widths=cell_widths(length,p.radial,ratio)
            self.preview.setText(f'N={p.radial}\nh_last/h_first={ratio:g}\nh_first={widths[0]:.7g} m\nh_last={widths[-1]:.7g} m')
            note=text('This changes actual radial simpleGrading in blockMesh.','此设置修改 blockMesh 的真实径向 simpleGrading。')
        elif local:
            self.preview.setText(f'R{index+1} · {self.direction.currentText()}\nh_start={self.region_fields["size"].value():g} m\nh_end={self.region_fields["size"].value()*ratio:g} m')
            note=text('This local region does not refine an O-grid. Select a Gmsh or partitioned-box generator first.','局部区域不加密 O 网格；请先选择 Gmsh 或分块矩形生成器。') if unsupported else text('These are target sizes; verify actual cells after Generate/check.','这些是目标间距；生成/检查后核对实际单元。')
        else:
            self.preview.setText(text('No local region exists yet.','尚未建立局部区域。')); note=text('Click Draw a refinement region, then click two corners in the sketch.','点击绘制加密区域，再在截面图中点击两个角点。')
        if p.mesh_method.startswith('Manual topology'):
            self.apply_refinement_button.setEnabled(False); note=text('Manual topology uses its own closed-region and curve assignments. Open Manual topology editor; legacy rectangular size controls are retained for automatic methods.','手动拓扑使用自身的闭合区域与边指派。请打开手动拓扑编辑器；旧矩形尺寸控制保留给自动生成器。')
        self.refinement_note.setText(note)

    def commit(self,candidate,message):
        try: candidate.validate()
        except Exception as e:
            self.feedback.setStyleSheet('color:#b02c24;'); self.feedback.setText(text('Not applied: ','未应用：')+str(e)); return False
        self.window.canvas.remember(); self.window.project=candidate; self.window.canvas.project=candidate; self.window.canvas.rebuild(); self.window.refresh_tree(); self.reload()
        self.feedback.setStyleSheet('color:#187657;'); self.feedback.setText(message); self.window.statusBar().showMessage(message,7000); return True

    def apply_generator(self):
        candidate=copy.deepcopy(self.window.project)
        for key,widget in self.fields.items(): setattr(candidate,key,widget.currentData() if key=='mesh_method' else widget.value())
        if candidate.dimension==2: candidate.spanwise=1
        self.commit(candidate,text('Generator settings applied; regenerate/check the mesh.','生成器设置已应用；请重新生成并检查网格。'))

    def apply_refinement(self):
        index=self.target.currentData()
        if index is None or not self.apply_refinement_button.isEnabled(): return
        candidate=copy.deepcopy(self.window.project); ratio=self.actual_ratio()
        if index==-1: candidate.grading=ratio
        else: candidate.regions[index].update({k:widget.value() for k,widget in self.region_fields.items()}); candidate.regions[index].update(ratio=ratio,direction='uniform' if self.mode.currentIndex()==0 else self.direction.currentText())
        self.commit(candidate,text('Spacing settings applied; regenerate/check the mesh.','间距设置已应用；请重新生成并检查网格。'))
