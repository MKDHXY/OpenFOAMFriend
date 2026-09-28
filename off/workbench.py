"""Optional, evidence-driven workflow; no CFD or mesh approval is fabricated."""
import hashlib,json
from dataclasses import asdict
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QListWidget,QListWidgetItem,QPushButton,QHBoxLayout
from .i18n import text

MESH_KEYS=('dimension','xmin','xmax','ymin','ymax','depth','shapes','regions','mesh_method','radial','circumferential','spanwise','outer_radius','grading','cell_size','smoothing','nonortho_limit','skew_limit','manual_mesh')
GEOMETRY_KEYS=('dimension','xmin','xmax','ymin','ymax','depth','shapes','manual_mesh')
PHYSICS_KEYS=('reference_length','velocity','viscosity','turbulence','turbulence_intensity','turbulence_length','sa_viscosity_ratio','transition_retheta','intermittency','dynamic_seed','end_time','delta_t','write_interval','max_co','cores','n_outer_correctors','n_correctors','n_nonorthogonal_correctors','momentum_predictor','dictionary_overrides')

def signature(value,keys=None):
    d=value if isinstance(value,dict) else asdict(value)
    if keys:
        raw=d; d={k:raw.get(k,{}) for k in keys}
        if keys==MESH_KEYS:
            d['manual_blockMeshDict']=raw.get('dictionary_overrides',{}).get('system/blockMeshDict')
    else: d={k:v for k,v in d.items() if k not in ('name','schema')}
    return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def geometry_check(p):
    p.validate()
    if p.mesh_method!='Structured cylinder O-grid' and not p.mesh_method.startswith('Manual topology'):
        for s in p.shapes:
            if s['x']-s['width']/2<=p.xmin or s['x']+s['width']/2>=p.xmax or s['y']-s['height']/2<=p.ymin or s['y']+s['height']/2>=p.ymax:
                raise ValueError(text('An obstacle touches or exceeds the rectangular domain.','实体接触或超出矩形流场。'))
    return True

class WorkflowGuide(QWidget):
    def __init__(self,window):
        super().__init__(); self.window=window; self.step=0; self.confirmed={}; self.connection_signature=None
        self.setMinimumWidth(0); self.setMaximumWidth(360); box=QVBoxLayout(self)
        self.heading=QLabel(); self.heading.setStyleSheet('font-size:17px;font-weight:600;color:#155976'); box.addWidget(self.heading)
        self.steps=QListWidget(); self.steps.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.steps.setFixedHeight(180); self.steps.currentRowChanged.connect(self.choose); box.addWidget(self.steps)
        self.description=QLabel(); self.description.setWordWrap(True); box.addWidget(self.description)
        self.evidence=QLabel(); self.evidence.setWordWrap(True); self.evidence.setStyleSheet('background:#e8f1f7;padding:12px;'); box.addWidget(self.evidence)
        self.action=QPushButton(); self.action.setMinimumHeight(40); self.action.clicked.connect(self.execute); box.addWidget(self.action)
        self.configure=QPushButton(); self.configure.clicked.connect(self.settings); box.addWidget(self.configure)
        nav=QHBoxLayout(); self.back=QPushButton(); self.next=QPushButton(); self.back.clicked.connect(lambda:self.choose(self.step-1)); self.next.clicked.connect(self.advance); nav.addWidget(self.back); nav.addWidget(self.next); box.addLayout(nav)
        self.note=QLabel(); self.note.setWordWrap(True); box.addWidget(self.note); box.addStretch(); self.refresh()

    def matching(self,mesh=False):
        keys=MESH_KEYS if mesh else None; target=signature(self.window.project,keys)
        return sorted([j for j in self.window.jobs if (mesh or not j.get('mesh_only')) and signature(j['project'],keys)==target],key=lambda j:j['created'])

    def state(self):
        p=self.window.project
        probe={'distro':self.window.profile.distro,'bashrc':self.window.profile.bashrc,'run_dir':self.window.profile.run_dir}
        ready=[self.connection_signature==signature(probe),self.confirmed.get('geometry')==signature(p,GEOMETRY_KEYS),False,self.confirmed.get('physics')==signature(p,PHYSICS_KEYS),False,False]
        meshes=self.matching(True); solves=self.matching(False); mesh=meshes[-1] if meshes else None; solve=solves[-1] if solves else None
        ready[2]=bool(mesh and mesh['state']=='DONE' and mesh.get('quality',{}).get('passed'))
        ready[4]=bool(solve); ready[5]=bool(solve and solve['state']=='DONE' and solve.get('time',0)>=p.end_time)
        return ready,mesh,solve

    def choose(self,row):
        if not 0<=row<6: return
        self.step=row
        self.refresh()

    def refresh(self):
        ready,mesh,solve=self.state(); self.ready=ready
        names=[text('Connection','WSL 连接'),text('Geometry','几何与区域'),text('Mesh & quality','网格与质量'),text('Physics & time','物理与时间'),text('Submit & monitor','提交与监控'),text('Results & export','结果与导出')]
        self.heading.setText(text('Guided simulation workflow','引导式仿真流程'))
        self.steps.blockSignals(True); self.steps.clear()
        for i,name in enumerate(names):
            flag=text('Ready','已核验') if ready[i] else text('Required','待完成')
            if i==2 and mesh and not ready[i]: flag=text('State: ','状态：')+mesh['state']
            if i==4 and solve: flag=solve['state']
            item=QListWidgetItem(f'{i+1:02d}  {name}  ·  {flag}');item.setToolTip(item.text()); item.setForeground(QColor('#187657' if ready[i] else '#36516a')); self.steps.addItem(item)
        self.steps.setCurrentRow(self.step); self.steps.blockSignals(False)
        instructions=[
            text('Configure this computer’s WSL distribution, OpenFOAM environment and CPU budget. Verify the actual executable before continuing.','配置本机 WSL、OpenFOAM 环境与核心预算，核验真实可执行程序。'),
            text('Draw parts in Geometry only. Set domain and SI dimensions, then explicitly review the geometry. This validates inputs, not mesh quality.','仅在几何工作区绘制实体。设定流场与 SI 尺寸后核验几何；此步骤核验输入，不代表网格质量通过。'),
            text('Use the mesh assistant or manual controls. Generate a genuine preview and inspect checkMesh. Changes to geometry or mesh settings invalidate matching evidence.','使用网格助手或手动区域生成真实预览，检查 checkMesh。几何或网格参数修改后，旧网格证据不再匹配。'),
            text('Review viscosity, velocity, turbulence model, time controls and output spacing. Input review does not prove temporal or physical convergence.','核验速度、黏度、湍流模型、时间控制与场输出间隔。输入核验不代表时间或物理收敛。'),
            text('Submit the current design snapshot after all four preparation steps are ready. The queue reserves real CPU cores and exposes pause / continue.','前四步核验后提交当前设计快照。队列按真实核心预算调度，支持暂停与继续。'),
            text('Open the completed matching case. Inspect fields and actual saved times, then use Postprocess to export PNG, GIF, CSV or MAT.','打开与当前设计匹配的已完成算例，检查场与真实保存时间，通过后处理导出 PNG、GIF、CSV 或 MAT。')]
        self.description.setText(instructions[self.step])
        detail=text('No verified evidence for this step yet.','该步骤尚无核验证据。')
        if self.step==0 and ready[0]: detail=text('Actual WSL/OpenFOAM executable probe passed.','真实 WSL/OpenFOAM 可执行程序核验通过。')
        elif self.step==1 and ready[1]: detail=text('Current geometry inputs reviewed; editing invalidates this review.','当前几何输入已核验，编辑后需重新核验。')
        elif self.step==2 and mesh:
            q=mesh.get('quality',{}); detail=f"{mesh['name']}\n{mesh['state']} · cells={q.get('cells','—')}\nskew={q.get('skewness','—')} · angle={q.get('non_orthogonality','—')}°"
        elif self.step==3 and ready[3]: detail=text('Current solver inputs reviewed.','当前求解参数已核验。')
        elif self.step in (4,5) and solve: detail=f"{solve['name']}\n{solve['state']} · t={solve.get('time',0):g} / {self.window.project.end_time:g} s"
        self.evidence.setText(detail)
        labels=[text('Verify WSL connection','核验 WSL 连接'),text('Review current geometry','核验当前几何'),text('Generate / inspect mesh','生成 / 检查网格'),text('Review current physics','核验当前物理设置'),text('Submit current design','提交当前设计'),text('Open verified result','打开已核验结果')]
        if self.step==2 and ready[2]: labels[2]=text('Open checked mesh','打开已检查网格')
        if self.step==4 and solve: labels[4]=text('Show submitted case','查看已提交算例')
        self.action.setText(labels[self.step]); self.action.setEnabled(self.step!=5 or ready[5])
        if self.step==4 and not solve: self.action.setEnabled(all(ready[:4]))
        configs=[text('WSL settings','WSL 设置'),text('Domain settings','流场设置'),text('Mesh controls','网格控制'),text('Physics settings','物理设置'),text('CPU / polling settings','核心 / 轮询设置'),text('Show result scene','查看结果场景')]
        self.configure.setText(configs[self.step]); self.back.setText(text('Back','上一步')); self.next.setText(text('Next','下一步')); self.back.setEnabled(self.step>0); self.next.setEnabled(self.step<5 and ready[self.step])
        self.note.setText(text('Optional guide. Expert mode remains available. Status comes from current inputs and actual case evidence; it is not a convergence certificate.','引导模式可选，可随时切换专家模式。状态来自当前输入与真实算例证据，不等于收敛认证。'))

    def execute(self):
        w=self.window
        try:
            if self.step==0:
                from .backend import probe
                config={'distro':w.profile.distro,'bashrc':w.profile.bashrc,'run_dir':w.profile.run_dir}; captured=signature(config)
                def done(result): self.connection_signature=captured; w.log.appendPlainText('WSL PROBE\n'+result); self.refresh()
                w.task(lambda:probe(w.profile),done)
            elif self.step==1: geometry_check(w.project); self.confirmed['geometry']=signature(w.project,GEOMETRY_KEYS); self.refresh()
            elif self.step==2:
                ready,mesh,_=self.state()
                if ready[2]: self.open_case(mesh,True)
                else: w.mesh_only()
            elif self.step==3: w.project.validate(); self.confirmed['physics']=signature(w.project,PHYSICS_KEYS); self.refresh()
            elif self.step==4:
                ready,_,solve=self.state()
                if solve: self.select_case(solve); w.tabs.setCurrentIndex(2)
                elif all(ready[:4]): w.submit()
            elif self.step==5:
                ready,_,solve=self.state()
                if ready[5]: self.open_case(solve)
        except Exception as e: w.error(str(e))

    def settings(self):
        [self.window.connection,self.window.domain_settings,lambda:self.window.open_mesh_properties('generator'),lambda:self.window.open_workspace_properties('physics'),self.window.connection,lambda:self.window.open_workspace_properties('results')][self.step]()
        self.refresh()

    def select_case(self,j):
        self.window.jobtable.selectRow(next(i for i,x in enumerate(self.window.jobs) if x['id']==j['id']))

    def open_case(self,j,mesh=False):
        self.select_case(j); self.window.open_job('Mesh' if mesh else None)

    def advance(self):
        if self.state()[0][self.step] and self.step<5: self.choose(self.step+1)
