"""Persistent physics, PIMPLE and scene pages, reached by parent and leaf clicks."""
import copy,json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QLabel,QTabWidget,QScrollArea,QComboBox,QSpinBox,QCheckBox,QPushButton,QHBoxLayout
from .numeric_controls import ScientificSpin
from .i18n import text
from .physics import MODELS,MODEL_DESCRIPTIONS_ZH

PHYSICS=('velocity','viscosity','turbulence','turbulence_intensity','turbulence_length')
SOLVER=('end_time','delta_t','write_interval','max_co','cores','n_outer_correctors','n_correctors','n_nonorthogonal_correctors','momentum_predictor')
LABELS={
 'velocity':('Free-stream U / m·s⁻¹','自由来流 U / m·s⁻¹'),'viscosity':('Kinematic nu / m²·s⁻¹','运动黏度 nu / m²·s⁻¹'),'turbulence':('Flow model','流动模型'),
 'turbulence_intensity':('Intensity I / fraction','湍流强度 I / 比例'),'turbulence_length':('Turbulence L / m','湍流长度 L / m'),
 'end_time':('End time / s','结束时间 / s'),'delta_t':('Max internal step / s','最大内部时间步 / s'),'write_interval':('Saved-field interval / s','场保存间隔 / s'),'max_co':('Maximum Courant number','最大库朗数'),'cores':('MPI ranks','MPI 进程数'),
 'n_outer_correctors':('PIMPLE outer correctors','PIMPLE 外迭代次数'),'n_correctors':('Pressure correctors','压力校正次数'),'n_nonorthogonal_correctors':('Non-orthogonal correctors','非正交校正次数'),'momentum_predictor':('Momentum predictor','动量预测')}

class WorkspaceProperties(QWidget):
 def __init__(self,window):
  super().__init__();self.window=window;self.signatures={};self.fields={};self.labels={};self.setMinimumWidth(295)
  box=QVBoxLayout(self);self.heading=QLabel();self.heading.setWordWrap(True);self.heading.setStyleSheet('font-weight:600;color:#155976');box.addWidget(self.heading);self.pages=QTabWidget();box.addWidget(self.pages,1)
  self.buttons={};self.notes={}
  for route,keys in [('physics',PHYSICS),('solver',SOLVER)]:
   page=QWidget();pagebox=QVBoxLayout(page);pagebox.setContentsMargins(0,0,0,0);body=QWidget();scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn);scroll.setWidget(body);pagebox.addWidget(scroll,1);self.pages.addTab(page,route);layout=QVBoxLayout(body);form=QFormLayout();form.setRowWrapPolicy(QFormLayout.WrapLongRows);layout.addLayout(form)
   for key in keys:
    if key=='turbulence':
     widget=QComboBox()
     for name,model in MODELS.items():widget.addItem(model.family+' · '+name,name)
     widget.setMaxVisibleItems(24);widget.currentIndexChanged.connect(self.describe)
    elif key=='momentum_predictor':widget=QCheckBox()
    elif key in ('cores','n_outer_correctors','n_correctors','n_nonorthogonal_correctors'):
     widget=QSpinBox();widget.setRange(0 if key=='n_nonorthogonal_correctors' else 1,1024)
    else:widget=ScientificSpin();widget.setRange(1e-14,1e12)
    widget.setObjectName('property_'+key);self.fields[key]=widget;label=QLabel();label.setWordWrap(True);self.labels[key]=label;form.addRow(label,widget)
   note=QLabel();note.setWordWrap(True);self.notes[route]=note;layout.addWidget(note)
   button=QPushButton();button.setObjectName('apply_'+route);button.clicked.connect(lambda checked=False,r=route:self.apply(r));self.buttons[route]=button;pagebox.addWidget(button)
   advanced=QPushButton();advanced.setObjectName('advanced_'+route);advanced.clicked.connect(window.flow_settings if route=='physics' else window.initial_files);self.buttons['advanced_'+route]=advanced;pagebox.addWidget(advanced);layout.addStretch()
  result=QWidget();layout=QVBoxLayout(result);resultscroll=QScrollArea();resultscroll.setWidgetResizable(True);resultscroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn);resultscroll.setWidget(result);self.pages.addTab(resultscroll,'results');self.result_info=QLabel();self.result_info.setWordWrap(True);layout.addWidget(self.result_info)
  self.result_buttons={}
  for key,en,zh,fn in [('queue','Select a case in the queue','到队列选择算例',lambda:window.tabs.setCurrentIndex(2)),('load','Open selected case result','打开所选算例结果',window.open_job),('mesh','Show actual mesh','查看真实网格',lambda:self.show_field('Mesh')),('pressure','Show pressure p','查看压力 p',lambda:self.show_field('p')),('csv','Export CSV…','导出 CSV…',window.csv),('mat','Export PINN MAT…','导出 PINN MAT…',window.mat),('gif','Export genuine-frame GIF…','导出真实帧 GIF…',window.gif),('foam','Export complete .foam case…','导出完整 .foam 算例…',window.export_foam_case)]:
   button=QPushButton();button.setObjectName('result_'+key);button.clicked.connect(fn);layout.addWidget(button);self.result_buttons[key]=(button,en,zh)
  layout.addStretch();self.feedback=QLabel();self.feedback.setWordWrap(True);self.feedback.setObjectName('workspacePropertyFeedback');box.addWidget(self.feedback)
  window.jobtable.itemSelectionChanged.connect(self.refresh_results);window.viewer.field.currentIndexChanged.connect(self.refresh_results);self.reload();self.pages.currentChanged.connect(lambda index:window.open_workspace_properties(("physics","solver","results")[index]))
 def retranslate(self):
  self.heading.setText(text('Physics / PIMPLE / results','物理 / PIMPLE / 结果'))
  for i,(en,zh) in enumerate([('Physics','物理'),('PIMPLE','PIMPLE'),('Results','结果')]):self.pages.setTabText(i,text(en,zh))
  for key,label in self.labels.items():label.setText(text(*LABELS[key]))
  for route in ('physics','solver'):self.buttons[route].setText(text('Apply physics parameters' if route=='physics' else 'Apply solver / output parameters','应用物理参数' if route=='physics' else '应用求解 / 输出参数'))
  self.buttons['advanced_physics'].setText(text('All model fields / advanced settings…','全部模型初始场 / 高级设置…'));self.buttons['advanced_solver'].setText(text('Review actual dictionaries / overrides…','查看实际字典 / 覆盖…'))
  self.notes['solver'].setText(text('PIMPLE → system/fvSolution. Time/output → system/controlDict. Ranks → system/decomposeParDict. Saved-field spacing differs from the internal timestep. Explicit code overrides take precedence; affected overrides must be removed before applying here.','PIMPLE → system/fvSolution；时间/输出 → system/controlDict；进程 → system/decomposeParDict。场保存间隔不同于内部时间步。显式代码覆盖优先，须先移除受影响覆盖再在此应用。'))
  for button,en,zh in self.result_buttons.values():button.setText(text(en,zh))
  self.describe();self.refresh_results();self.feedback.clear()
 def reload(self,page=None):
  self.retranslate()
  for route,keys in [('physics',PHYSICS),('solver',SOLVER)]:
   sig=json.dumps([getattr(self.window.project,k) for k in keys])
   if self.signatures.get(route)==sig:continue
   self.signatures[route]=sig
   for key in keys:
    widget=self.fields[key];value=getattr(self.window.project,key)
    if isinstance(widget,QComboBox):widget.setCurrentIndex(widget.findData(value))
    elif isinstance(widget,QCheckBox):widget.setChecked(value)
    else:widget.setValue(value)
  self.describe()
  if page:self.pages.setCurrentIndex({'physics':0,'solver':1,'results':2}[page])
 def describe(self,*args):
  if 'physics' not in self.notes:return
  name=self.fields['turbulence'].currentData()
  if name in MODELS:self.notes['physics'].setText(text(MODELS[name].description,MODEL_DESCRIPTIONS_ZH[name])+text('\nSources: constant/physicalProperties, constant/momentumTransport, model initial fields.','\n对应：constant/physicalProperties、constant/momentumTransport 与模型初始场。'))
 def apply(self,route):
  p=self.window.project;candidate=copy.deepcopy(p);keys=PHYSICS if route=='physics' else SOLVER
  try:
   affected={'constant/physicalProperties','constant/momentumTransport','0/U'} if route=='physics' else {'system/controlDict','system/fvSolution','system/decomposeParDict'}
   overrides=affected&set(p.dictionary_overrides)
   if overrides:raise ValueError(text('Remove/review affected explicit overrides before applying: ','请先移除/核对受影响的显式覆盖：')+', '.join(sorted(overrides)))
   for key in keys:
    widget=self.fields[key];value=widget.currentData() if isinstance(widget,QComboBox) else widget.isChecked() if isinstance(widget,QCheckBox) else widget.value();setattr(candidate,key,value)
   candidate.validate()
   for key in keys:setattr(p,key,getattr(candidate,key))
   self.window.refresh_tree();self.feedback.setStyleSheet('color:#187657');self.feedback.setText(text('Applied. New cases use these values; existing running cases are unchanged.','已应用，新算例使用这些参数，已有运行算例不受修改。'))
  except Exception as e:self.feedback.setStyleSheet('color:#ab302b');self.feedback.setText(text('Not applied: ','未应用：')+str(e))
 def refresh_results(self,*args):
  if not hasattr(self,'result_info'):return
  result=self.window.viewer.result;row=self.window.jobtable.currentRow();jobs=self.window.jobs;selected=jobs[row] if 0<=row<len(jobs) else None
  if result:self.result_info.setText(text('Loaded actual data: ','已加载真实数据：')+result.foam.parent.name+'\n'+text('Saved frames: ','保存帧数：')+str(len(result.times)))
  if result:self.result_info.setToolTip(str(result.foam))
  else:self.result_info.setText(text('No result is loaded. Select a completed case in the queue, then Open selected case result. Mesh/field export stays disabled until real data is loaded.','尚未加载结果。到队列选择完成算例，再打开所选算例结果；加载真实数据前网格/场导出禁用。'))
  self.result_buttons['load'][0].setEnabled(bool(selected and selected['state']=='DONE'))
  for key in ('mesh','pressure','csv','mat','gif','foam'):self.result_buttons[key][0].setEnabled(result is not None)
 def show_field(self,name):
  if not self.window.viewer.result:return
  i=self.window.viewer.field.findData(name)
  if i<0:self.feedback.setText(text('Field unavailable: ','场不存在：')+name);return
  self.window.tabs.setCurrentIndex(1);self.window.viewer.field.setCurrentIndex(i);self.feedback.setText(text('Displaying real field: ','正在显示真实场：')+name)
