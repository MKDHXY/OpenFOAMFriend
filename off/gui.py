"""Dockable desktop workbench. Geometry, jobs and VTK use real backend data."""
import json, copy, os, traceback, subprocess, sys, time
from pathlib import Path
from dataclasses import asdict
from PySide6.QtCore import Qt,QTimer,QThread,Signal,QUrl
from PySide6.QtGui import QAction,QDesktopServices,QColor,QIcon
from PySide6.QtWidgets import *
from .models import Project,Profile,load_profile,save_profile
from .backend import Engine,BASE,probe
from .quality import audit
from .canvas import Canvas
from .viewer import Viewer
from . import i18n
from .i18n import tr,text,translate_widgets
from .mesh_assistant import MeshAssistant
from .dictionary_editor import DictionaryDialog
from .workbench import WorkflowGuide
from .grading import GradingDialog
from .compact_navigation import StageNavigation,DockableStageToolBar
from .design3d import Design3D
from .domain_dialog import DomainDialog

STYLE='''QMainWindow,QDialog{background:#eef3f8;color:#19344f;} QToolBar{background:#173b5d;spacing:6px;padding:6px;} QToolBar QToolButton{color:white;padding:7px;border-radius:3px;} QToolBar QToolButton:checked{background:#008fa6;} QTabWidget::pane{border:1px solid #c7d5e2;} QTabBar::tab{padding:10px 20px;background:#dce6ef;} QTabBar::tab:selected{background:white;border-bottom:3px solid #008fa6;} QDockWidget::title{padding:7px;background:#dce6ef;} QPushButton{background:#fff;border:1px solid #b6c9da;border-radius:4px;padding:7px 12px;} QPushButton:hover{background:#d5edf6;} QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{background:white;border:1px solid #b6c9da;padding:5px;} QTreeWidget,QTableWidget,QPlainTextEdit{background:white;border:1px solid #c7d5e2;} QHeaderView::section{background:#e0eaf3;padding:7px;border:0px;} QLabel{padding:2px;}'''

class Worker(QThread):
    success=Signal(object); error=Signal(str)
    def __init__(self,fn,parent): super().__init__(parent); self.fn=fn
    def run(self):
        try: self.success.emit(self.fn())
        except Exception: self.error.emit(traceback.format_exc())

class Properties(QDialog):
    def __init__(self,title,data,parent,choices=None,integer=(),sections=None,scientific=False):
        super().__init__(parent); self.setWindowTitle(tr(title)); self.setMinimumWidth(460); self.inputs={}; self.data=data
        layout=QVBoxLayout(self); form=QFormLayout(); forms={}
        if sections:
            tabs=QTabWidget(); layout.addWidget(tabs)
            for title,keys in sections:
                page=QWidget(); group=QFormLayout(page); tabs.addTab(page,title)
                for key in keys: forms[key]=group
        else: layout.addLayout(form)
        for key,val in data.items():
            if choices and key in choices:
                inp=QComboBox()
                for option in choices[key]: inp.addItem(tr(option),option)
                inp.setCurrentIndex(inp.findData(str(val)))
            elif isinstance(val,int) or key in integer: inp=QSpinBox(); inp.setRange(1,1000000); inp.setValue(int(val))
            elif isinstance(val,float):
                from .numeric_controls import ScientificSpin
                inp=ScientificSpin() if scientific else QDoubleSpinBox(); inp.setDecimals(16 if scientific else 12); inp.setRange(-1e9,1e9); inp.setValue(val); inp.setSingleStep(.1)
            else: inp=QLineEdit(str(val))
            self.inputs[key]=inp; forms.get(key,form).addRow(tr(key.replace('_',' ').title()),inp)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        translate_widgets(self)
    def values(self):
        return {k:v.currentData() if isinstance(v,QComboBox) else v.value() if isinstance(v,(QSpinBox,QDoubleSpinBox)) else v.text() for k,v in self.inputs.items()}

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); i18n.initialize(); self.setWindowIcon(QIcon(str(BASE/'assets/icon.ico'))); self.setWindowTitle('Open Foam Friend | zongxuan & hanwen | '+BASE.name); self.resize(1500,930); self.setStyleSheet(STYLE)
        self.project=Project(name='Cylinder_'+time.strftime('%Y%m%d_%H%M%S')); self.profile=load_profile(); self.engine=Engine(self.profile); self.workers=[]; self.jobs=[]; self.polling=False; self.preview_job_id=None
        self.activity=QProgressBar(); self.activity.setRange(0,0); self.activity.setMaximumWidth(140); self.activity.hide(); self.statusBar().addPermanentWidget(self.activity); self.busy_tasks=0
        self.tabs=QTabWidget(); self.setCentralWidget(self.tabs); self.canvas=Canvas(self.project); self.canvas.changed.connect(self.refresh_tree); self.canvas.position.connect(self.statusBar().showMessage); self.tabs.addTab(self.canvas,'01  GEOMETRY')
        self.canvas.editRequested.connect(self.edit_canvas_object)
        self.viewer=Viewer(); self.viewer.info.connect(self.statusBar().showMessage); self.tabs.addTab(self.viewer,'02  SCENES')
        self.jobtable=QTableWidget(0,9); self.jobtable.setHorizontalHeaderLabels(['Case','Stage','Cores','Simulated t / s','Progress','Max Co (latest)','Elapsed','ETA estimate','Mesh quality']); self.jobtable.setSelectionBehavior(QAbstractItemView.SelectRows); self.jobtable.setEditTriggers(QAbstractItemView.NoEditTriggers); self.jobtable.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); self.jobtable.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); self.jobtable.itemSelectionChanged.connect(self.job_selected)
        queue=QWidget(); qlayout=QVBoxLayout(queue); buttons=QGridLayout()
        for label,fn in [('Submit design',self.submit),('Pause',lambda:self.signal('STOP')),('Continue',lambda:self.signal('CONT')),('Recover checkpoint',self.recover),('Cancel',self.cancel),('Earlier',lambda:self.reorder(-1)),('Later',lambda:self.reorder(1)),('Open result',self.open_job),('Folder',self.folder_job),('Refresh',self.poll)]:
            button=QPushButton(label); button.clicked.connect(fn); n=buttons.count(); buttons.addWidget(button,n//5,n%5)
        qlayout.addLayout(buttons); qlayout.addWidget(self.jobtable); self.tabs.addTab(queue,'03  RUN QUEUE')
        self.stage_nav=StageNavigation(self); self.stage_toolbar=DockableStageToolBar(self); self.stage_toolbar.setObjectName('workspaceStageTabs'); self.stage_toolbar.setMovable(True); self.stage_toolbar.setFloatable(False); self.stage_toolbar.setAllowedAreas(Qt.TopToolBarArea|Qt.BottomToolBarArea); self.stage_toolbar.setStyleSheet('QToolBar{background:#e8edf2;padding:0px;border-top:1px solid #cad4de;}'); self.stage_toolbar.addWidget(self.stage_nav); self.stage_toolbar.toggleViewAction().setEnabled(False)
        area=Qt.TopToolBarArea if i18n.preferences().get('workspace_tab_area','bottom')=='top' else Qt.BottomToolBarArea
        self.addToolBar(area,self.stage_toolbar)
        self.stage_toolbar.setContextMenuPolicy(Qt.CustomContextMenu); self.stage_toolbar.customContextMenuRequested.connect(self.stage_position_menu)
        workspace=QWidget(); layout=QVBoxLayout(workspace); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0); layout.addWidget(self.stage_nav.header); layout.addWidget(self.tabs,1); self.tabs.tabBar().hide(); self.setCentralWidget(workspace)
        self.tabs.removeTab(0); self.preprocess=QWidget(); prelayout=QVBoxLayout(self.preprocess); prelayout.setContentsMargins(0,0,0,0); row=QHBoxLayout(); self.pre_mode=QTabBar(); self.pre_mode.setExpanding(False); self.pre_mode.addTab(text('Design','设计')); self.pre_mode.addTab(text('Meshing','网格')); self.pre_mode.addTab(text('Manual topology','手动拓扑')); row.addWidget(self.pre_mode); self.dimension_action=QPushButton(); self.dimension_action.clicked.connect(self.domain_settings); row.addWidget(self.dimension_action)
        self.design_view=QComboBox(); self.design_view.addItem('XY sketch',0); self.design_view.addItem('3D extrusion model',1); row.addWidget(self.design_view); self.selection_label=QLabel(); row.addWidget(self.selection_label); row.addStretch(); prelayout.addLayout(row)
        self.design_stack=QStackedWidget(); self.design_stack.addWidget(self.canvas); self.design3d=Design3D(self); self.design_stack.addWidget(self.design3d)
        from .manual_editor import ManualEditor
        self.manual_editor=ManualEditor(self); self.design_stack.addWidget(self.manual_editor); prelayout.addWidget(self.design_stack,1)
        self.tabs.insertTab(0,self.preprocess,'01  GEOMETRY'); self.tabs.setCurrentIndex(0)
        self.design_view.currentIndexChanged.connect(self.change_design_view); self.canvas.selectionChanged.connect(self.design_selection); self.design3d.selected.connect(self.canvas.select_tags)
        self.tree=QTreeWidget(); self.tree.setHeaderLabels(['Simulation objects']); self.tree.itemDoubleClicked.connect(self.edit_object); self.tree_dock=self.dock('Simulation tree',self.tree,Qt.LeftDockWidgetArea); self.tree_dock.setMinimumWidth(190)
        self.tree.itemClicked.connect(self.tree_select); self.tree.itemActivated.connect(self.activate_tree_navigation)
        inspector=QScrollArea(); inspector.setWidgetResizable(True); inspector.setMinimumWidth(280); inspector.setMaximumWidth(360); content=QWidget(); inspector.setWidget(content); form=QVBoxLayout(content)
        self.summary=QLabel(); self.summary.setWordWrap(True); form.addWidget(self.summary)
        self.context_buttons=[]
        for label,fn,pages in [('Domain & dimension',self.domain_settings,(0,)),('Automatic mesh assistant',self.auto_mesh,(0,)),('Mesh generation settings',self.mesh_settings,(0,)),('Flow & solver settings',self.flow_settings,(0,)),('WSL connection & CPU budget',self.connection,(0,2)),('Generate / check mesh only',self.mesh_only,(0,)),('Locate worst skewness',lambda:self.quality_view('skewness'),(1,)),('Locate worst non-orthogonality',lambda:self.quality_view('nonorthogonality'),(1,)),('View / edit case dictionaries',self.dictionaries,(1,2))]:
            b=QPushButton(label); b.clicked.connect(fn); form.addWidget(b); self.context_buttons.append((b,pages))
        form.addStretch(); self.inspector_stack=QStackedWidget(); self.inspector_stack.addWidget(inspector)
        from .mesh_inspector import MeshInspector
        self.mesh_inspector=MeshInspector(self); self.inspector_stack.addWidget(self.mesh_inspector); self.inspector_dock=self.dock('Properties & workflow',self.inspector_stack,Qt.RightDockWidgetArea)
        from .workspace_properties import WorkspaceProperties
        self.workspace_properties=WorkspaceProperties(self); self.inspector_stack.addWidget(self.workspace_properties); self.active_property_route=None
        self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFont(__import__('PySide6.QtGui',fromlist=['QFont']).QFont('Consolas',10)); self.log.setMaximumBlockCount(2000); self.log.setMinimumHeight(110); self.dock('Evidence / solver log',self.log,Qt.BottomDockWidgetArea)
        self.guide=WorkflowGuide(self); guide_scroll=QScrollArea(); guide_scroll.setWidgetResizable(True); guide_scroll.setWidget(self.guide); guide_scroll.setMinimumWidth(245)
        self.guide_dock=self.dock('Guided workflow',guide_scroll,Qt.LeftDockWidgetArea); self.splitDockWidget(self.tree_dock,self.guide_dock,Qt.Vertical)
        toolbar=self.addToolBar('Geometry tools'); toolbar.setMovable(False); self.sketch_toolbar=toolbar
        group=None
        from PySide6.QtGui import QActionGroup
        group=QActionGroup(self); group.setExclusive(True)
        self.tool_actions={}
        for label,tool in [('Select','select'),('Pan','pan'),('Line','line'),('Polyline','polyline'),('Polygon solid','polygon'),('Circle','circle'),('Rectangle','rectangle'),('Triangle','triangle'),('Mesh region','region'),('Eraser','erase'),('Measure','measure')]:
            a=QAction(label,self); a.setCheckable(True); group.addAction(a); a.triggered.connect(lambda checked,t=tool:self.canvas.set_tool(t)); toolbar.addAction(a)
            self.tool_actions[tool]=a
            a.setToolTip(text('Continuous tool. Middle drag: pan; wheel: zoom; Esc: cancel.','连续绘制工具。中键拖动平移；滚轮缩放；Esc 取消。'))
            if tool=='select': a.setChecked(True)
        toolbar.addSeparator()
        for label,fn in [('Undo',self.canvas.undo),('Redo',self.canvas.redo),('Fit',self.canvas.fit)]: toolbar.addAction(label,fn)
        self.snap_actions={}
        for label,key in [('Object snap F3','object_snap'),('Ortho F8','ortho'),('Grid snap F9','grid_snap')]:
            action=toolbar.addAction(label); action.setCheckable(True); action.setChecked(getattr(self.canvas,key)); action.triggered.connect(lambda checked,k=key:(setattr(self.canvas,k,checked),self.canvas.toolChanged.emit(self.canvas.tool))); self.snap_actions[key]=action
        self.tool_hint=QLabel(); self.statusBar().addPermanentWidget(self.tool_hint); self.canvas.toolChanged.connect(self.sync_drawing)
        self.addToolBarBreak(); workflow=self.addToolBar('Geometry operations'); workflow.setMovable(False); self.geometry_toolbar=workflow
        for label,fn in [('Precise shape',self.precise_shape),('Exact line',self.exact_line),('Mesh spacing',self.spacing),('Initial fields / dictionaries',self.initial_files),('Sketch settings',self.sketch_settings),('Automatic mesh assistant',self.auto_mesh)]: workflow.addAction(label,fn)
        self.scene_toolbar=self.addToolBar('Scene operations'); self.scene_toolbar.setMovable(False)
        for label,fn in [('Fit',self.viewer.fit),('Locate worst skewness',lambda:self.quality_view('skewness')),('Export screenshot PNG…',self.png)]:
            a=self.scene_toolbar.addAction(label,fn)
            if label=='Export screenshot PNG…': self.scene_png_action=a
        self.queue_toolbar=self.addToolBar('Queue operations'); self.queue_toolbar.setMovable(False)
        for label,fn in [('Refresh',self.poll),('WSL connection & CPU budget',self.connection),('View / edit case dictionaries',self.dictionaries)]: self.queue_toolbar.addAction(label,fn)
        self.mesh_toolbar=self.addToolBar(text('Meshing operations','网格操作')); self.mesh_toolbar.setMovable(False); self.mesh_region_action=self.mesh_toolbar.addAction('Draw refinement region'); self.mesh_region_action.setCheckable(True); self.mesh_region_action.triggered.connect(lambda checked:self.draw_refinement_region() if checked else self.canvas.set_tool('select'))
        for label,fn in [('Manual topology editor',self.open_manual_topology),('Mesh generation settings',self.mesh_settings),('Mesh spacing',self.spacing),('Automatic mesh assistant',self.auto_mesh),('Generate / check mesh only',self.mesh_only),('Generated design files',self.generated_files)]: self.mesh_toolbar.addAction(label,fn)
        self.pre_mode.currentChanged.connect(self.pre_mode_changed)
        menu=self.menuBar().addMenu('Project')
        for label,fn in [('New cylinder project',self.preset),('Open project…',self.load_project),('Save project…',self.save_project),('Import .foam result…',self.import_foam),('Open WSL run folder',self.run_folder),('WSL configuration…',self.connection),('Exit',self.close)]: menu.addAction(label,fn)
        menu.addAction('Typical flow starters…',self.typical_flows)
        files_menu=self.menuBar().addMenu('Files'); files_menu.addAction('Generated design files…',self.generated_files); files_menu.addAction('Selected case — all files…',self.case_files); files_menu.addAction('OpenFOAM run directory — all files…',self.run_files); files_menu.addAction('Application source — all files…',self.source_files)
        export=self.menuBar().addMenu('Postprocess')
        self.export_actions=[]
        for label,fn in [('Export screenshot PNG…',self.png),('Export real-frame GIF…',self.gif),('Export configurable CSV…',self.csv),('Export PINN MAT…',self.mat)]: self.export_actions.append(export.addAction(label,fn))
        self.fft_action=export.addAction('Force history & single-sided FFT',self.force_plot)
        settings=self.menuBar().addMenu('Settings'); settings.addAction('Language / 语言',self.language_settings); self.sketch_settings_action=settings.addAction('Sketch settings',self.sketch_settings)
        self.guide_action=settings.addAction('Guided workflow'); self.guide_action.setCheckable(True); self.guide_action.toggled.connect(self.set_guided)
        settings.addAction('Reset workspace layout',self.reset_layout)
        settings.addAction('SSH / Slurm supercomputer',self.ssh_settings)
        helpmenu=self.menuBar().addMenu('Help'); helpmenu.addAction('Website support',lambda:QDesktopServices.openUrl(QUrl('http://spaceaero.space'))); helpmenu.addAction('User guide EN',lambda:self.manual('EN')); helpmenu.addAction('使用说明 中文',lambda:self.manual('ZH')); helpmenu.addAction('About',lambda:QMessageBox.information(self,'Open Foam Friend',text('Authors: zongxuan and hanwen\nEngineering release 0.17.0\nQt + VTK + Gmsh + OpenFOAM 14\nHelp: http://spaceaero.space','作者：zongxuan 和 hanwen\n工程版本 0.17.0\nQt + VTK + Gmsh + OpenFOAM 14\n帮助：http://spaceaero.space')))
        helpmenu.addAction('Quick tutorials…',self.quick_tutorials)
        self.tabs.currentChanged.connect(self.context_update)
        workflow.addAction('Design parameters / mesh code',self.design_code)
        command_handlers={'Precise shape':self.precise_shape,'Exact line':self.exact_line,'Mesh spacing':self.spacing,'Initial fields / dictionaries':self.initial_files,'Sketch settings':self.sketch_settings,'Automatic mesh assistant':self.auto_mesh,'Design parameters / mesh code':self.design_code}
        for action in workflow.actions():
            original=action.text(); action.triggered.disconnect(); action.setCheckable(True); action.setProperty('off_command',True)
            action.triggered.connect(lambda checked=False,a=action,fn=command_handlers[original]:self.invoke_command(a,fn))
        menu.addAction('Welcome / Projects',self.welcome)
        menu.addAction('Detect WSL / OpenFOAM',self.detect_wsl)
        settings.addAction('WSL Terminal',self.open_terminal)
        self.export_actions.append(export.addAction('Export complete .foam case folder',self.export_foam_case))
        from .tool_icons import tool_icon
        for bar in (self.sketch_toolbar,self.geometry_toolbar,self.scene_toolbar,self.queue_toolbar):
            bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            for action in bar.actions():
                if not action.isSeparator(): action.setIcon(tool_icon(action.text()))
        self.setStyleSheet(STYLE+""" QToolBar{background:#f1f3f5;spacing:2px;padding:3px;border-bottom:1px solid #ccd3da;} QToolBar QToolButton{color:#243e53;border:0;border-bottom:2px solid transparent;background:transparent;padding:5px 7px;border-radius:0;} QToolBar QToolButton:hover{background:#e0e7ed;} QToolBar QToolButton:pressed{background:#cadde8;border-bottom:2px solid #177ba0;} QToolBar QToolButton:checked{background:#d7e8f0;border-bottom:2px solid #177ba0;font-weight:600;} QToolBar QToolButton:disabled{color:#8996a0;background:transparent;} QPushButton:pressed{background:#c9e1eb;border-color:#177ba0;} QPushButton:disabled{color:#8292a1;background:#e6ebef;}""")
        for button in self.findChildren(QPushButton): button.pressed.connect(lambda b=button:self.statusBar().showMessage(text('Selected: ','已点击：')+b.text(),4000))
        for action in self.findChildren(QAction): action.triggered.connect(lambda checked=False,a=action:self.statusBar().showMessage(text('Action: ','操作：')+a.text(),4000))
        self.mode_widget=QWidget(); self.mode_widget.setMaximumWidth(580); self.mode_widget.setStyleSheet('QPushButton{padding:3px 6px;} QComboBox{padding:3px;}'); mode_row=QHBoxLayout(self.mode_widget); mode_row.setContentsMargins(4,0,4,0)
        self.mode_label=QLabel(text('Workflow:','工作方式：')); mode_row.addWidget(self.mode_label); self.mode_combo=QComboBox(); self.mode_combo.setObjectName('workflowMode')
        self.mode_combo.addItem(text('Expert','专家模式'),False); self.mode_combo.addItem(text('Guided','引导模式'),True); mode_row.addWidget(self.mode_combo)
        self.expert_button=QPushButton(text('Expert tools…','专家工具…')); self.expert_button.clicked.connect(self.expert_tools); mode_row.addWidget(self.expert_button)
        self.re_button=QPushButton(text('Reynolds…','雷诺数…')); self.re_button.clicked.connect(self.reynolds_settings); mode_row.addWidget(self.re_button)
        self.advice_button=QPushButton(text('Setup advice…','设置建议…')); self.advice_button.clicked.connect(self.setup_advice); mode_row.addWidget(self.advice_button)
        self.menuBar().setCornerWidget(self.mode_widget,Qt.TopRightCorner); self.mode_combo.currentIndexChanged.connect(lambda index:self.set_guided(bool(self.mode_combo.itemData(index))))
        settings.addAction(text('Expert tools…','专家工具…'),self.expert_tools); settings.addAction(text('Reynolds number & scaling','雷诺数与联动设置'),self.reynolds_settings)
        self.guide_dock.visibilityChanged.connect(self.guide_visibility)
        self.guide_action.setChecked(i18n.preferences().get('guided',False)); self.set_guided(self.guide_action.isChecked())
        self.timer=QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(self.profile.poll_seconds*1000); self.retranslate(); self.context_update(); self.poll()
        if (BASE/'data/remote_jobs.json').exists():
            from .ssh_gui import SSHDialog
            self.ssh_dialog=SSHDialog(self)
    def dock(self,title,widget,area):
        d=QDockWidget(title,self); d.setWidget(widget); self.addDockWidget(area,d); return d
    def task(self,fn,done=None):
        worker=Worker(fn,self); self.workers.append(worker); worker.error.connect(self.error); self.busy_tasks+=1; self.activity.show(); self.statusBar().showMessage(text('Working… See evidence log for details.','正在处理…详情见证据日志。'))
        sender=getattr(self,'initiating_action',None) or self.sender(); disabled=isinstance(sender,(QPushButton,QAction)) and sender.isEnabled()
        if disabled: sender.setEnabled(False)
        if isinstance(sender,QAction) and sender.property('off_command'): sender.setProperty('off_pending',True)
        def finish():
            self.workers.remove(worker); self.busy_tasks-=1; self.activity.setVisible(self.busy_tasks>0)
            if disabled: sender.setEnabled(True)
            if isinstance(sender,QAction) and sender.property('off_command'): sender.setProperty('off_pending',False); sender.setChecked(False)
            self.context_update(); self.statusBar().showMessage(text('Operation finished.','操作结束。'),5000)
        worker.success.connect(done or (lambda x:self.log.appendPlainText(str(x)))); worker.finished.connect(finish); worker.start()
    def invoke_command(self,action,fn):
        """A command stays visually active while its dialog or worker is active."""
        action.setChecked(True); self.initiating_action=action
        self.statusBar().showMessage(text('Executing: ','正在执行：')+action.text())
        from PySide6.QtCore import QEventLoop
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        try: fn()
        finally:
            self.initiating_action=None
            if not action.property('off_pending'): action.setChecked(False); self.statusBar().showMessage(text('Closed: ','已结束：')+action.text(),5000)
    def design_code(self):
        from .workspace_tools import DesignCodeDialog
        dialog=DesignCodeDialog(self.project,self)
        if dialog.exec():
            self.canvas.remember(); self.project=dialog.result_project; self.canvas.project=self.project; self.canvas.rebuild(); self.canvas.fit(); self.refresh_tree()
    def detect_wsl(self):
        from .workspace_tools import discover_wsl
        def done(records):
            self.log.appendPlainText(json.dumps(records,indent=2)); options=[]; profiles=[]
            for record in records:
                for bashrc in record.get('bashrcs',[]):
                    version=__import__('re').search(r'openfoam(\d+)',bashrc)
                    run=record.get('runs',[]); fallback=record['home']+'/OpenFOAM/'+record['user']+(version.group(1) if version else '')+'/run'
                    profiles.append(Profile(record['distro'],bashrc,run[-1] if run else fallback,min(4,record.get('cores') or 4),self.profile.poll_seconds)); options.append(f"{record['distro']} · {bashrc} · {profiles[-1].run_dir}")
            if not options: return QMessageBox.information(self,'WSL discovery / 自动探测','No OpenFOAM bashrc found. See log and configure manually. / 未找到安装，请查看日志并手动配置。')
            choice,ok=QInputDialog.getItem(self,'WSL / OpenFOAM detected','Apply detected machine profile / 应用探测配置',options,0,False)
            if ok:
                candidate=profiles[options.index(choice)]
                def apply(result):
                    self.profile=candidate; save_profile(candidate); self.engine.profile=candidate; self.timer.setInterval(candidate.poll_seconds*1000); self.refresh_tree(); self.log.appendPlainText('Verified profile / 已验证配置\n'+result)
                self.task(lambda:probe(candidate),apply)
        self.task(discover_wsl,done)
    def open_terminal(self):
        from .workspace_tools import Terminal
        if not hasattr(self,'terminal'):
            self.terminal=Terminal(self.profile,self); self.terminal_dock=self.dock('WSL Terminal',self.terminal,Qt.BottomDockWidgetArea)
        self.terminal_dock.show(); self.terminal_dock.raise_(); self.terminal.command.setFocus()
    def remember_project(self,path):
        paths=[str(Path(path).resolve())]+[p for p in i18n.preferences().get('recent_projects',[]) if p!=str(Path(path).resolve())]; i18n.save_preference('recent_projects',paths[:15])
    def load_project_path(self,path):
        try: self.tabs.setCurrentIndex(0); self.project=Project.load(path); self.canvas.project=self.project; self.canvas.history.clear(); self.canvas.future.clear(); self.canvas.rebuild(); self.canvas.fit(); self.refresh_tree(); self.remember_project(path)
        except Exception as e: self.error(str(e))
    def welcome(self):
        dialog=QDialog(self); dialog.setObjectName('welcomeProjects'); dialog.resize(760,500); box=QVBoxLayout(dialog)
        langrow=QHBoxLayout();langrow.addStretch();langrow.addWidget(QLabel('Language / 语言'));lang=QComboBox();lang.setObjectName('welcomeLanguage');lang.addItem('中文','zh');lang.addItem('English','en');lang.setCurrentIndex(lang.findData(i18n.LANG));langrow.addWidget(lang);box.addLayout(langrow)
        heading=QLabel();box.addWidget(heading);recent=QLabel();box.addWidget(recent);table=QListWidget();box.addWidget(table)
        for path in i18n.preferences().get('recent_projects',[]):
            item=QListWidgetItem(Path(path).stem+'\n'+path); item.setData(Qt.UserRole,path); table.addItem(item)
        table.itemDoubleClicked.connect(lambda item:(dialog.accept(),self.load_project_path(item.data(Qt.UserRole))))
        row=QHBoxLayout()
        def fresh(dimension):
            dialog.accept(); self.preset(); self.project.dimension=dimension; self.project.spanwise=1 if dimension==2 else 4; self.refresh_tree()
        labels=[]
        for en,zh,fn in [('New 2D','新建二维',lambda:fresh(2)),('New 3D','新建三维',lambda:fresh(3)),('Open project','打开项目',lambda:(dialog.accept(),self.load_project())),('Guide EN','英文教程',lambda:self.manual('EN')),('Guide ZH','中文教程',lambda:self.manual('ZH'))]:
            button=QPushButton();button.clicked.connect(fn);row.addWidget(button);labels.append((button,en,zh))
        box.addLayout(row);show=QCheckBox();show.setChecked(i18n.preferences().get('show_welcome',True));show.toggled.connect(lambda value:i18n.save_preference('show_welcome',value));box.addWidget(show);close=QPushButton();close.setObjectName('welcomeContinue');close.clicked.connect(dialog.accept);box.addWidget(close)
        def translate_welcome():
            dialog.setWindowTitle(text('Open Foam Friend · Projects','Open Foam Friend · 项目'));heading.setText(text('Open Foam Friend — zongxuan & hanwen\nDesign → Mesh quality → Solve → Genuine results','Open Foam Friend — zongxuan & hanwen\n设计 → 网格质量 → 求解 → 真实结果'));recent.setText(text('Recent projects (double-click to open)','最近项目（双击打开）'));show.setText(text('Show at startup','启动时显示'));close.setText(text('Continue workspace','进入工作台'))
            for button,en,zh in labels:button.setText(text(en,zh))
        lang.currentIndexChanged.connect(lambda _:(self.change_language(lang.currentData()),translate_welcome()));translate_welcome();dialog.exec()
    def export_foam_case(self):
        from .workspace_tools import export_case
        if not self.viewer.result: return self.error('Load a finished serial .foam result first.')
        source=self.viewer.result.foam
        for job in self.engine.store.all():
            if Path(job['case'])==source.parent and job['state'] not in ('DONE','FAILED','CANCELLED'): return self.error('Wait until the case stops before exporting.')
        parent=QFileDialog.getExistingDirectory(self,'Export complete CFD case / 导出完整算例',str(BASE))
        if not parent: return
        target=Path(parent)/(source.parent.name+'_export_'+time.strftime('%Y%m%d_%H%M%S'))
        self.task(lambda:export_case(source,target),lambda result:(self.log.appendPlainText(json.dumps(result,indent=2)),os.startfile(target)))
    def error(self,details): self.log.appendPlainText(details); QMessageBox.warning(self,tr('Operation failed'),details[-1800:])
    def language_settings(self):
        dialog=QDialog(self); dialog.setWindowTitle('Language / 语言'); box=QVBoxLayout(dialog); box.addWidget(QLabel('Interface language / 界面语言')); combo=QComboBox(); combo.addItem('中文','zh'); combo.addItem('English','en'); combo.setCurrentIndex(combo.findData(i18n.LANG)); box.addWidget(combo); buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); box.addWidget(buttons)
        if dialog.exec(): self.change_language(combo.currentData())
    def change_language(self,language): i18n.set_language(language); self.retranslate()
    def retranslate(self):
        if hasattr(self,'mode_combo'):
            self.mode_label.setText(text('Workflow:','工作方式：')); self.mode_combo.setItemText(0,text('Expert','专家模式')); self.mode_combo.setItemText(1,text('Guided','引导模式')); self.expert_button.setText(text('Expert tools…','专家工具…')); self.re_button.setText(text('Reynolds…','雷诺数…')); self.advice_button.setText(text('Setup advice…','设置建议…'))
        if hasattr(self,'pre_mode'): self.pre_mode.setTabText(0,text('Design','设计')); self.pre_mode.setTabText(1,text('Meshing','网格'))
        translate_widgets(self); self.mesh_inspector.retranslate(); self.workspace_properties.retranslate(); self.manual_editor.retranslate(); self.pre_mode.setTabText(2,text('Manual topology','手动拓扑')); self.viewer.retranslate(); self.refresh_tree(); self.canvas.rebuild(); self.canvas.viewport().update(); self.sync_drawing(self.canvas.tool); self.stage_nav.refresh()
    def change_design_view(self,index):
        if self.pre_mode.currentIndex()==2: return
        if index==1 and self.project.dimension!=3: self.design_view.setCurrentIndex(0); return
        self.design_stack.setCurrentIndex(index)
        if index==1: self.design3d.rebuild(self.project,fit=True); self.design3d.highlight([i.data(0) for i in self.canvas.scene().selectedItems() if i.data(0)])
        self.context_update()
    def design_selection(self,tags):
        if hasattr(self,'selection_label'): self.selection_label.setText(text('Selected: ','已选择：')+', '.join(f'{kind} {i+1}' for kind,i in tags) if tags else text('Click an object or its label to select','点击对象或文字标签选择'))
        if hasattr(self,'design3d') and self.design_stack.currentIndex()==1: self.design3d.highlight(tags)
    def activate_tree_navigation(self,item,col):
        tag=item.data(0,Qt.UserRole)
        # Persistent routes are idempotent; preserve original object-dialog double clicks.
        if tag and tag[0] in ('nav','nav_detail','mesh_editor','manual_editor'):self.edit_object(item,col)
    def tree_select(self,item,col):
        tag=item.data(0,Qt.UserRole)
        if tag and tag[0] in ('nav','nav_detail') and tag[1] in ('physics','solver','results'):return self.open_workspace_properties(tag[1])
        if tag and tag[0]=='manual_editor': return self.open_manual_topology()
        if tag and tag[0]=='mesh_editor': return self.open_mesh_properties(tag[1])
        if tag==('nav','mesh'): return self.open_mesh_properties('generator')
        if tag and tag[0] in ('shape','region','curve'):
            self.tabs.setCurrentIndex(0); self.pre_mode.setCurrentIndex(1 if tag[0]=='region' else 0); self.canvas.select_tags([tag])
            if tag[0]=='region': self.open_mesh_properties('refinement',tag[1])
    def sync_drawing(self,tool):
        if tool in self.tool_actions: self.tool_actions[tool].setChecked(True)
        for key,action in self.snap_actions.items(): action.setChecked(getattr(self.canvas,key))
        if hasattr(self,'mesh_region_action'): self.mesh_region_action.setChecked(tool=='region')
        self.tool_hint.setText(text(f'{tool.upper()} · Shift: orthogonal · Alt: free · Esc: cancel · MMB: pan',f'{tr(tool.title())} · Shift 正交 · Alt 自由 · Esc 取消 · 中键平移'))
    def set_guided(self,enabled):
        self.guide_action.blockSignals(True); self.guide_action.setChecked(enabled); self.guide_action.blockSignals(False)
        self.guide_dock.setVisible(enabled); i18n.save_preference('guided',enabled)
        if enabled: self.guide_dock.raise_()
        else: self.inspector_dock.raise_()
        if hasattr(self,'mode_combo'):
            self.mode_combo.blockSignals(True); self.mode_combo.setCurrentIndex(1 if enabled else 0); self.mode_combo.blockSignals(False)
            self.expert_button.setEnabled(not enabled)
        self.guide.refresh()
    def expert_tools(self):
        dialog=QDialog(self); dialog.setWindowTitle(text('Expert workbench','专家工作台')); box=QVBoxLayout(dialog)
        note=QLabel(text('Direct access; existing tools remain available in both modes.','直接访问专业设置；两种模式均保留原有工具。')); note.setWordWrap(True); box.addWidget(note)
        for label,fn in [(text('Reynolds & scaling','雷诺数与联动'),self.reynolds_settings),(text('Evidence-based setup advice','有依据的设置建议'),self.setup_advice),(text('Models / solver / time / cores','模型 / 求解器 / 时间 / 核心数'),self.flow_settings),(text('Mesh resolution / grading','网格分辨率 / 渐变'),self.mesh_settings),(text('Initial fields & dictionaries','初始场与字典'),self.initial_files),(text('Design / mesh code','设计 / 网格代码'),self.design_code),(text('WSL terminal','WSL 终端'),self.open_terminal),(text('SSH / Slurm','SSH / Slurm'),self.ssh_settings)]:
            button=QPushButton(label); box.addWidget(button); button.clicked.connect(lambda checked=False,f=fn:(dialog.accept(),QTimer.singleShot(0,f)))
        dialog.exec()
    def reynolds_settings(self):
        from .reynolds_gui import ReynoldsDialog
        dialog=ReynoldsDialog(self.project,self)
        if dialog.exec():
            self.project=dialog.result_project; self.canvas.project=self.project; self.canvas.rebuild(); self.refresh_tree()
    def setup_advice(self):
        from .advisor import mesh_signature
        from .advisor_gui import AdviceDialog
        from .meshmetrics import measure
        p=copy.deepcopy(self.project)
        try:
            from .reynolds import reference
            reference(p)
        except ValueError as e: return self.error(str(e))
        target=mesh_signature(p); jobs=self.engine.store.all(); matches=[j for j in jobs if j['state']=='DONE' and mesh_signature(j['project'])==target and (Path(j['case'])/'constant/polyMesh/points').exists()]
        def show(evidence):
            if asdict(self.project)!=asdict(p): return self.error(text('Design changed during measurement; reopen advice.','测量期间设计已变化，请重新打开建议。'))
            dialog=AdviceDialog(p,evidence,self)
            if dialog.exec() and dialog.result_project:
                self.project=dialog.result_project; self.canvas.project=self.project; self.canvas.rebuild(); self.refresh_tree()
        if matches:
            case=matches[-1]['case']
            def inspect():
                case_project=json.loads((Path(case)/'off_project.json').read_text(encoding='utf-8'))
                if mesh_signature(case_project)!=target: raise ValueError('Actual case project metadata differs from the current design.')
                quality,metrics=measure(case,p.skew_limit,p.nonortho_limit); return {'case':case,'mesh_signature':target,'quality':quality,'metrics':metrics}
            self.task(inspect,show)
        else: show(None)
    def guide_visibility(self,visible):
        from shiboken6 import isValid
        if isValid(self) and isValid(self.guide_dock) and isValid(self.guide_action) and self.isVisible():
            self.guide_action.setChecked(not self.guide_dock.isHidden())
    def reset_layout(self):
        self.position_stage_tabs(Qt.BottomToolBarArea)
        for d in self.findChildren(QDockWidget):
            d.setFloating(False)
            if d is not self.guide_dock: d.show()
        self.addDockWidget(Qt.LeftDockWidgetArea,self.tree_dock); self.addDockWidget(Qt.RightDockWidgetArea,self.inspector_dock); self.addDockWidget(Qt.LeftDockWidgetArea,self.guide_dock)
        self.splitDockWidget(self.tree_dock,self.guide_dock,Qt.Vertical); self.set_guided(self.guide_action.isChecked())
        self.resizeDocks([self.tree_dock,self.inspector_dock],[280,300],Qt.Horizontal)
        self.context_update()
    def context_update(self,*args):
        if hasattr(self,'workspace_properties'): self.workspace_properties.refresh_results()
        page=self.tabs.currentIndex()
        manual=page==0 and self.pre_mode.currentIndex()==2
        if hasattr(self,'guide_dock'):
            if manual and not hasattr(self,'manual_dock_restore'):
                self.manual_dock_restore=[(dock,not dock.isHidden(),dock.isVisible()) for dock in (self.inspector_dock,)]
                for dock,visible,active in self.manual_dock_restore: dock.blockSignals(True); dock.hide(); dock.blockSignals(False)
            elif not manual and hasattr(self,'manual_dock_restore'):
                for dock,visible,active in self.manual_dock_restore: dock.blockSignals(True); dock.setVisible(visible); dock.blockSignals(False); dock.raise_() if active else None
                del self.manual_dock_restore
        if hasattr(self,'inspector_stack') and (page!=0 or self.pre_mode.currentIndex()!=1):
            route=getattr(self,'active_property_route',None)
            self.inspector_stack.setCurrentIndex(self.inspector_stack.indexOf(self.guided_form) if route=='guided_form' and hasattr(self,'guided_form') else 1 if route=='mesh' and page==0 else 2 if (route in ('physics','solver') and page==0) or (route=='results' and page==1) else 0)
        self.stage_nav.refresh()
        self.tool_hint.setVisible(page==0)
        sketch=page==0 and self.design_stack.currentIndex()==0
        meshing=page==0 and hasattr(self,'pre_mode') and self.pre_mode.currentIndex()==1
        self.sketch_toolbar.setVisible(sketch and not meshing); self.geometry_toolbar.setVisible(page==0 and self.pre_mode.currentIndex()==0)
        if hasattr(self,'mesh_toolbar'): self.mesh_toolbar.setVisible(meshing)
        self.tool_actions['region'].setVisible(False)
        for action in self.geometry_toolbar.actions():
            if action.property('off_mesh_only') is None: action.setProperty('off_mesh_only',action.text() in ('Mesh spacing','Automatic mesh assistant','网格间距','自动网格助手'))
            action.setVisible(not action.property('off_mesh_only'))
        self.scene_toolbar.setVisible(page==1); self.queue_toolbar.setVisible(page==2)
        for toolbar,index in ((self.sketch_toolbar,0),(self.geometry_toolbar,0),(self.scene_toolbar,1),(self.queue_toolbar,2)): toolbar.toggleViewAction().setEnabled(page==index)
        for a in self.sketch_toolbar.actions(): a.setEnabled(sketch)
        if hasattr(self,'mesh_toolbar'):
            for a in self.mesh_toolbar.actions(): a.setEnabled(page==0)
        for a in self.geometry_toolbar.actions(): a.setEnabled(page==0 and not a.property('off_pending'))
        self.sketch_settings_action.setEnabled(page==0)
        for b,pages in self.context_buttons:
            label=b.property('off_original') or b.text(); mesh_control=label in ('Automatic mesh assistant','Mesh generation settings','Generate / check mesh only')
            b.setVisible(page in pages and (page!=0 or not mesh_control or meshing))
        for a in self.export_actions: a.setEnabled(page==1 and self.viewer.result is not None)
        self.scene_png_action.setEnabled(page==1 and self.viewer.result is not None)
        self.fft_action.setEnabled(page in (1,2) and self.jobtable.currentRow()>=0)
        self.update_summary()
    def update_summary(self):
        p=self.project; page=self.tabs.currentIndex()
        from .reynolds import reference
        try: d=reference(p)[0]; re_text=f'{p.velocity*d/p.viscosity:.5g}'
        except ValueError: re_text=text('Set reference L','需指定参考 L')
        if page==0:
            self.summary.setText(text(f'Geometry workspace\n{p.name}\n{p.dimension}D · {p.mesh_method}\nRe = {re_text}\n\nDouble-click: dimensions · Ctrl+D: duplicate\nCtrl+Z / Y: undo / redo\nRulers: {self.canvas.unit}; snap {self.canvas.snap:g} m',f'几何工作区\n{p.name}\n{p.dimension}D · {tr(p.mesh_method)}\nRe = {re_text}\n\n双击：精确尺寸 · Ctrl+D：复制\nCtrl+Z / Y：撤销 / 重做\n标尺：{self.canvas.unit}；吸附 {self.canvas.snap:g} m'))
        elif page==1:
            self.summary.setText(text('Scene workspace\nReal OpenFOAM mesh / saved fields\n\nUse the field, slice and time controls. Quality-location tools refer to the selected queue case. Drawing tools are available only in Geometry.','场景工作区\n真实 OpenFOAM 网格 / 保存场\n\n使用场变量、切片与时间控制。质量定位工具针对选中的队列算例。绘图工具仅属于几何工作区。'))
        else:
            self.summary.setText(text(f'Solver queue\nCPU budget: {self.profile.max_cores}\nPoll: {self.profile.poll_seconds} s\n\nSelect a case for its actual log, dictionaries, pause/resume and results. Preparation controls are in Geometry or the optional guide.',f'求解队列\n核心预算：{self.profile.max_cores}\n轮询：{self.profile.poll_seconds} s\n\n选择算例查看真实日志、字典、暂停/继续与结果。准备操作位于几何工作区或可选引导流程。'))
    def sketch_settings(self):
        dlg=Properties(tr('Sketch settings'),{'snap_spacing_m':float(self.canvas.snap),'display_unit':self.canvas.unit},self,{'display_unit':['m','cm','mm']})
        if dlg.exec():
            values=dlg.values()
            if values['snap_spacing_m']<0: return self.error(text('Snap spacing must be >=0; zero disables it.','吸附间距须 ≥0，设为 0 可关闭。'))
            self.canvas.snap=values['snap_spacing_m']; self.canvas.unit=values['display_unit']; self.canvas.viewport().update(); self.refresh_tree()
    def precise_shape(self):
        dlg=Properties(tr('Precise shape'),{'kind':'circle','name':'body'+str(len(self.project.shapes)+1),'x':0.,'y':0.,'width':1.,'height':1.},self,{'kind':['circle','rectangle','triangle']})
        if dlg.exec():
            s=dlg.values()
            if s['width']<=0 or s['height']<=0: return self.error(text('Positive dimensions required.','尺寸必须为正。'))
            if s['kind']=='circle': s['height']=s['width']
            self.canvas.remember(); self.project.shapes.append(s); self.canvas.compatible_mesher(); self.canvas.rebuild(); self.refresh_tree()
    def exact_line(self,index=None):
        if isinstance(index,bool): index=None
        c=self.project.curves[index] if index is not None else {'name':'Construction','points':[[0.,0.],[1.,0.]]}
        dialog=QDialog(self); dialog.setWindowTitle(text('Construction line / polyline — metres','辅助直线 / 折线 — 米')); box=QVBoxLayout(dialog); name=QLineEdit(c['name']); box.addWidget(name); box.addWidget(QLabel(text('One x, y pair per line. Open curves are construction references, not solid obstacles.','每行输入 x, y。开放曲线为辅助参考，不作为实体障碍物。'))); code=QPlainTextEdit('\n'.join(f'{x:g}, {y:g}' for x,y in c['points'])); box.addWidget(code); buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); box.addWidget(buttons)
        if dialog.exec():
            try:
                points=[[float(v) for v in line.replace(',',' ').split()] for line in code.toPlainText().splitlines() if line.strip()]
                if len(points)<2 or any(len(v)!=2 for v in points): raise ValueError('At least two x,y points required.')
                if not all(__import__('math').isfinite(v) for point in points for v in point): raise ValueError('Coordinates must be finite.')
                if index is None: self.canvas.add_curve(points,name.text())
                else: self.canvas.remember(); self.project.curves[index]={'name':name.text(),'points':points}; self.canvas.rebuild(); self.refresh_tree()
            except Exception as e: self.error(str(e))
    def spacing(self): self.open_mesh_properties('refinement')
    def spacing_dialog(self):
        dialog=GradingDialog(self.project,self)
        if dialog.exec(): self.canvas.remember(); dialog.apply(); self.canvas.rebuild(); self.refresh_tree()
    def initial_files(self):
        from .backend import write_case,DATA
        try:
            draft=DATA/'drafts'/('draft_'+time.strftime('%Y%m%d_%H%M%S')); write_case(self.project,self.profile,preview_root=draft)
            dialog=DictionaryDialog(draft,lambda:True,self,preferred='0/U'); dialog.exec()
            if dialog.editor.document().isModified():
                if QMessageBox.question(self,text('Unsaved changes','未保存修改'),text('Save the current dictionary before applying?','应用前保存当前文件？'))==QMessageBox.Yes: dialog.save_current()
            from .physics import EDITABLE_KEYS
            keys=EDITABLE_KEYS
            original=DATA/'drafts'/('baseline_'+time.strftime('%Y%m%d_%H%M%S')); baseline=copy.deepcopy(self.project); baseline.dictionary_overrides={}; write_case(baseline,self.profile,preview_root=original)
            overrides={key:(draft/key).read_text(encoding='utf-8') for key in keys if (draft/key).exists() and (draft/key).read_text(encoding='utf-8')!=(original/key).read_text(encoding='utf-8')}
            old=self.project.dictionary_overrides; self.project.dictionary_overrides=overrides
            try: self.project.validate()
            except Exception: self.project.dictionary_overrides=old; raise
            self.log.appendPlainText(text('Explicit dictionary overrides: ','显式字典覆盖：')+', '.join(overrides)); self.refresh_tree()
        except Exception as e: self.error(str(e))
    def ssh_settings(self):
        from .ssh_gui import SSHDialog
        if not hasattr(self,'ssh_dialog'): self.ssh_dialog=SSHDialog(self)
        self.ssh_dialog.show(); self.ssh_dialog.raise_(); self.ssh_dialog.activateWindow()
    def position_stage_tabs(self,area):
        self.addToolBar(area,self.stage_toolbar); i18n.save_preference('workspace_tab_area','top' if area==Qt.TopToolBarArea else 'bottom')
    def stage_position_menu(self,pos):
        menu=QMenu(self)
        menu.addAction(text('Dock at top','停靠到上方'),lambda:self.position_stage_tabs(Qt.TopToolBarArea))
        menu.addAction(text('Dock at bottom (default)','停靠到下方（默认）'),lambda:self.position_stage_tabs(Qt.BottomToolBarArea))
        menu.exec(self.stage_toolbar.mapToGlobal(pos))
    def edit_canvas_object(self,kind,index):
        item=QTreeWidgetItem(); item.setData(0,Qt.UserRole,(kind,index)); self.edit_object(item,0)
    def auto_mesh(self):
        dialog=MeshAssistant(self.project,self)
        if dialog.exec():
            self.project=dialog.result_project; self.canvas.project=self.project; self.canvas.rebuild(); self.canvas.fit(); self.refresh_tree()
            if dialog.generate: self.enqueue(True,preview=True)
    def selected_job(self):
        row=self.jobtable.currentRow()
        if row<0 or row>=len(self.jobs): raise ValueError('Select a queue row first.')
        return self.jobs[row]
    def refresh_tree(self):
        if hasattr(self,'dimension_action'):
            self.dimension_action.setText(text(f'{self.project.dimension}D · Model / domain…',f'{self.project.dimension}D · 模型 / 流场…')); self.design_view.setItemText(0,text('XY sketch','XY 截面绘图')); self.design_view.setItemText(1,text('3D extrusion model','三维拉伸模型')); self.design_view.model().item(1).setEnabled(self.project.dimension==3)
            if self.project.dimension==2: self.design_view.setCurrentIndex(0)
            if self.design_stack.currentIndex()==1: self.design3d.rebuild(self.project)
        p=self.project; self.tree.clear(); root=QTreeWidgetItem(self.tree,[p.name]); root.setData(0,Qt.UserRole,('project',0))
        geom=QTreeWidgetItem(root,[tr('Geometry / solid obstacles')])
        for i,s in enumerate(p.shapes): item=QTreeWidgetItem(geom,[f"{s['name']} ({s['kind']}) {s['width']:g} × {s['height']:g} m"]); item.setData(0,Qt.UserRole,('shape',i))
        mesh_branch=QTreeWidgetItem(root,[text('Mesh operations','网格操作')]); mesh_branch.setData(0,Qt.UserRole,('nav','mesh')); backend=QTreeWidgetItem(mesh_branch,[text('Backend: ','生成器：')+('blockMesh' if p.mesh_method.startswith('Structured') or p.mesh_method=='Manual topology (blockMesh)' else 'Gmsh → gmshToFoam')+' · '+tr(p.mesh_method)]); backend.setData(0,Qt.UserRole,('mesh_editor','generator')); backend.setToolTip(0,text('Click to open editable generator settings','点击打开可编辑的生成器设置'))
        regions=QTreeWidgetItem(mesh_branch,[text('Refinement / spacing regions (controls, not cells)','加密 / 间距区域（控制参数，不是已生成单元）')]); regions.setData(0,Qt.UserRole,('mesh_editor','refinement')); regions.setToolTip(0,text('Click to open spacing and refinement settings','点击打开间距与加密设置'))
        manual=QTreeWidgetItem(mesh_branch,[text('Manual topology: nodes / curves / regions','手动拓扑：节点 / 曲线 / 区域')]); manual.setData(0,Qt.UserRole,('manual_editor',0)); QTreeWidgetItem(manual,[str(len(p.manual_mesh.get('nodes',{})))+text(' nodes · ',' 节点 · ')+str(len(p.manual_mesh.get('edges',[])))+text(' curves',' 曲线')])
        curves=QTreeWidgetItem(root,[text('Construction curves (not obstacles)','辅助曲线（不参与实体切割）')])
        for i,c in enumerate(p.curves): item=QTreeWidgetItem(curves,[c['name']]); item.setData(0,Qt.UserRole,('curve',i))
        for i,r in enumerate(p.regions): item=QTreeWidgetItem(regions,[f"R{i+1} h={r['size']:g} {r['direction']} ratio={r['ratio']:g}"]); item.setData(0,Qt.UserRole,('region',i))
        for label,kind,value in [(text('Physics continuum','物理连续体'),'physics',f'{p.turbulence} · U={p.velocity:g} · nu={p.viscosity:g}'),(text('Solver & stopping criteria','求解器与停止条件'),'solver',f'PIMPLE {p.n_outer_correctors}/{p.n_correctors} · t_end={p.end_time:g} s · maxCo={p.max_co:g}'),(text('Scenes & reports','场景与报告'),'results',text('Mesh / fields / export','网格 / 场 / 导出'))]:
            branch=QTreeWidgetItem(root,[label]); branch.setData(0,Qt.UserRole,('nav',kind)); detail=QTreeWidgetItem(branch,[value]); detail.setData(0,Qt.UserRole,('nav_detail',kind)); tip=text('Click to open editable properties / result actions','点击打开可编辑属性 / 结果操作'); branch.setToolTip(0,tip); detail.setToolTip(0,tip)
        self.tree.expandAll(); self.update_summary()
        if hasattr(self,'workspace_properties'): self.workspace_properties.reload()
        if hasattr(self,'mesh_inspector'): self.mesh_inspector.reload()
        if hasattr(self,'manual_editor'): self.manual_editor.reload()
        if hasattr(self,'guide'): self.guide.refresh()
    def edit_object(self,item,col):
        tag=item.data(0,Qt.UserRole)
        if not tag: return
        kind,i=tag
        if kind in ('nav','nav_detail') and i in ('physics','solver','results'):return self.open_workspace_properties(i)
        if kind=='manual_editor': return self.open_manual_topology()
        if kind=='mesh_editor': return self.open_mesh_properties(i)
        if kind=='region': return self.open_mesh_properties('refinement',i)
        if kind=='nav':
            if i=='mesh': return self.open_mesh_properties('generator')
            if i=='physics': return self.flow_settings()
            self.tabs.setCurrentIndex(2 if i=='solver' else 1); return
        if kind=='project': return self.domain_settings()
        if kind=='curve': return self.exact_line(i)
        if kind=='shape' and self.project.shapes[i]['kind']=='polygon': return self.edit_polygon(i)
        self.tabs.setCurrentIndex(0)
        data=(self.project.shapes if kind=='shape' else self.project.regions)[i]
        choices={'direction':['uniform','x+','x-','y+','y-']} if kind=='region' else {'kind':['circle','rectangle','triangle']}
        dlg=Properties('Object dimensions / mesh control',data,self,choices)
        if dlg.exec():
            values=dlg.values()
            if kind=='shape' and values['kind']=='circle': values['height']=values['width']
            if any(not __import__('math').isfinite(float(values[k])) or values[k]<=0 for k in ('width','height')): return self.error(text('Positive finite dimensions required.','尺寸必须为有限正数。'))
            self.canvas.remember(); data.update(values); self.canvas.compatible_mesher(); self.canvas.rebuild(); self.refresh_tree()
    def edit_settings(self,title,keys,choices=None):
        dlg=Properties(title,{k:getattr(self.project,k) for k in keys},self,choices)
        if dlg.exec():
            old=copy.deepcopy(self.project)
            for k,v in dlg.values().items(): setattr(self.project,k,v)
            try: self.project.validate()
            except Exception as e: self.project=old; self.canvas.project=old; return self.error(str(e))
            self.canvas.rebuild(); self.canvas.fit(); self.refresh_tree()
    def domain_settings(self):
        dialog=DomainDialog(self.project,self)
        if self.guide_action.isChecked():
            def apply():
                candidate=copy.deepcopy(self.project)
                for key in ('name','dimension','xmin','xmax','ymin','ymax','depth','spanwise'):setattr(candidate,key,getattr(dialog.result_project,key))
                candidate.validate();self.project.__dict__.update(copy.deepcopy(candidate.__dict__));dialog.source=copy.deepcopy(self.project);self.canvas.project=self.project;self.canvas.rebuild();self.canvas.fit();self.refresh_tree()
            return self.embed_guided_dialog(dialog,apply)
        if dialog.exec():
            self.project=dialog.result_project; self.canvas.project=self.project; self.canvas.rebuild(); self.canvas.fit(); self.refresh_tree()
    def mesh_settings(self): self.open_mesh_properties('generator')
    def mesh_settings_dialog(self): self.edit_settings('Meshing',['mesh_method','radial','circumferential','spanwise','outer_radius','grading','cell_size','smoothing','nonortho_limit','skew_limit'],{'mesh_method':['Structured cylinder O-grid','Structured partitioned box','Gmsh triangle / prism','Gmsh quadrilateral / prism','Gmsh tetrahedral','Manual topology (blockMesh)','Manual topology (Gmsh)']})
    def flow_settings(self):
        from .physics import MODELS,MODEL_DESCRIPTIONS_ZH
        keys=['velocity','viscosity','turbulence','turbulence_intensity','turbulence_length','sa_viscosity_ratio','transition_retheta','intermittency','dynamic_seed','end_time','delta_t','write_interval','max_co','cores']
        dlg=Properties('Transient incompressible solver / SI',{k:getattr(self.project,k) for k in keys},self,{'turbulence':list(MODELS)},sections=[(text('Flow & model','流动与模型'),keys[:9]),(text('Time & parallel','时间与并行'),keys[9:])],scientific=True)
        labels={'velocity':text('Free-stream U / m·s⁻¹','自由来流 U / m·s⁻¹'),'viscosity':text('Kinematic nu / m²·s⁻¹','运动黏度 nu / m²·s⁻¹'),'turbulence_intensity':text('Intensity I / fraction','湍流强度 I / 比例'),'turbulence_length':text('Length scale L / m','湍流长度 L / m'),'sa_viscosity_ratio':text('SA nuTilda/nu / ratio','SA nuTilda/nu / 比值'),'transition_retheta':text('Transition ReThetat / —','转捩 ReThetat / —'),'intermittency':text('Intermittency gammaInt / —','间歇因子 gammaInt / —'),'dynamic_seed':text('Dynamic seed / m⁴·s⁻⁴','动态平均量 / m⁴·s⁻⁴'),'end_time':text('End time / s','结束时间 / s'),'delta_t':text('Max internal step / s','最大内部时间步 / s'),'write_interval':text('Saved-field interval / s','场保存间隔 / s'),'max_co':text('Maximum Co / —','最大 Co / —')}
        for key,label in labels.items(): dlg.inputs[key].parentWidget().layout().labelForField(dlg.inputs[key]).setText(label)
        dlg.setMinimumWidth(650); combo=dlg.inputs['turbulence']; combo.setMaxVisibleItems(24)
        for index in range(combo.count()):
            model=MODELS[combo.itemData(index)]; combo.setItemText(index,model.family+' · '+model.name)
        details=QLabel(); details.setWordWrap(True); details.setMinimumHeight(110); dlg.layout().insertWidget(0,details)
        def describe(*args):
            model=MODELS[combo.currentData()]
            for key,relevant in [('sa_viscosity_ratio','nuTilda'),('transition_retheta','ReThetat'),('intermittency','gammaInt'),('dynamic_seed','flm')]: dlg.inputs[key].setEnabled(relevant in model.fields)
            details.setText(text('Foundation 14 · transient incompressible Newtonian flow.\n','Foundation 14 · 瞬态不可压缩牛顿流体。\n')+text(model.description,MODEL_DESCRIPTIONS_ZH[model.name])+'\n'+text('Required fields: ','所需初始场：')+(', '.join(model.fields) or 'U, p')+'\n'+text('RAS uses transient PIMPLE (URANS). LES/DES requires 3D. This is a model setup, not a DNS/LES accuracy certificate. Edit initial fields and coefficients before production use.','RAS 使用瞬态 PIMPLE（URANS）。LES/DES 需要三维。模型设置不等于 DNS/LES 精度认证，正式计算前须核对初始场和模型系数。'))
        reset=QCheckBox(text('Reset model-specific field and numerical overrides on model change','切换模型时重置专属初始场及离散/求解覆盖')); reset.setChecked(False); reset.setEnabled(bool(self.project.dictionary_overrides)); reset.setToolTip(text('Optional and explicit: retain U, p and viscosity overrides; reset turbulence fields, momentumTransport, fvSchemes and fvSolution.','可选且须明确勾选：保留 U、p 和黏度覆盖，重置湍流场、momentumTransport、fvSchemes、fvSolution。')); dlg.layout().insertWidget(1,reset)
        combo.currentIndexChanged.connect(describe); describe()
        if dlg.exec():
            old=copy.deepcopy(self.project)
            for k,v in dlg.values().items(): setattr(self.project,k,v)
            if reset.isChecked() and self.project.turbulence!=old.turbulence:
                self.project.dictionary_overrides={key:value for key,value in self.project.dictionary_overrides.items() if (not key.startswith('0/') or key in ('0/U','0/p')) and key not in ('constant/momentumTransport','system/fvSchemes','system/fvSolution')}
            try: self.project.validate()
            except Exception as e: self.project=old; self.canvas.project=old; return self.error(str(e))
            self.canvas.rebuild(); self.refresh_tree()
    def connection(self):
        dlg=Properties('Machine-specific WSL profile',asdict(self.profile),self)
        def apply():
            p=Profile(**dlg.values())
            if p.poll_seconds<1 or p.max_cores<1 or not p.run_dir.startswith('/'): return self.error('Invalid CPU budget, polling interval or Linux case path.')
            self.profile=p; save_profile(p); self.engine.profile=p; self.timer.setInterval(p.poll_seconds*1000); self.refresh_tree(); self.task(lambda:probe(p),lambda x:self.log.appendPlainText('WSL PROBE\n'+x))
        if self.guide_action.isChecked():return self.embed_guided_dialog(dlg,apply)
        if dlg.exec():apply()
    def embed_guided_dialog(self,dialog,apply):
        """Reuse complete validated forms inside the inspector; no modal or floating page."""
        if hasattr(self,'guided_form'):
            self.inspector_stack.removeWidget(self.guided_form);self.guided_form.deleteLater()
        self.guided_form=QScrollArea();self.guided_form.setWidgetResizable(True);self.guided_form.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        dialog.setWindowFlags(Qt.Widget);dialog.setMinimumWidth(0);self.guided_form.setWidget(dialog);self.inspector_stack.addWidget(self.guided_form);self.active_property_route='guided_form';self.inspector_stack.setCurrentWidget(self.guided_form)
        def accepted():
            try:apply()
            except Exception as e:self.error(str(e));dialog.show();return
            dialog.show();self.statusBar().showMessage(text('Settings applied in the guided workspace.','已在当前引导工作区应用设置。'),5000)
        dialog.accepted.connect(accepted);dialog.rejected.connect(lambda:(setattr(self,'active_property_route',None),self.inspector_stack.setCurrentIndex(0)))
        self.inspector_dock.show();self.inspector_dock.raise_();dialog.show()
    def preset(self):
        self.tabs.setCurrentIndex(0); self.project=Project(name='Cylinder_'+time.strftime('%Y%m%d_%H%M%S')); self.canvas.project=self.project; self.canvas.history.clear(); self.canvas.future.clear(); self.canvas.rebuild(); self.canvas.fit(); self.refresh_tree()
    def save_project(self):
        path,_=QFileDialog.getSaveFileName(self,'Save reproducible project',str(BASE/'projects'/f'{self.project.name}.off.json'),'OFF Project (*.off.json)')
        if path:
            try: Path(path).parent.mkdir(parents=True,exist_ok=True); self.project.save(path); self.remember_project(path)
            except Exception as e: self.error(str(e))
    def load_project(self):
        path,_=QFileDialog.getOpenFileName(self,'Load project',str(BASE),'OFF Project (*.json)')
        if path:
            self.load_project_path(path)
    def submit(self): self.enqueue(False)
    def mesh_only(self): self.enqueue(True)
    def enqueue(self,mesh_only,preview=False):
        p=copy.deepcopy(self.project)
        if preview: p.name=p.name+'_Mesh_'+time.strftime('%H%M%S')
        self.statusBar().showMessage(text('Preparing actual case / mesh…','正在准备真实算例 / 网格…'))
        def done(j):
            self.log.appendPlainText(text('Queued real WSL case: ','已排队真实 WSL 算例：')+j['linux_case']); self.tabs.setCurrentIndex(2)
            if preview: self.preview_job_id=j['id']
            self.poll()
        self.task(lambda:self.engine.enqueue(p,mesh_only),done)
    def poll(self):
        if self.polling: return
        self.polling=True
        def done(jobs):
            if self.engine.last_poll_error:
                self.statusBar().showMessage(text('Monitoring delayed: showing cached states; retrying next poll.','监控延迟：当前显示缓存状态，下次轮询重试。'))
                if getattr(self,'last_poll_warning',None)!=self.engine.last_poll_error: self.log.appendPlainText(self.engine.last_poll_error)
            self.last_poll_warning=self.engine.last_poll_error
            self.polling=False; self.jobs=jobs; row=self.jobtable.currentRow(); self.jobtable.blockSignals(True); self.jobtable.setRowCount(len(jobs))
            for i,j in enumerate(jobs):
                fmt=lambda x:'—' if x is None else time.strftime('%H:%M:%S',time.gmtime(max(0,x)))
                values=[j['name'],tr(j['state']),str(j['project']['cores']),f"{j.get('time',0):.6g} / {j['project']['end_time']:g}",f"{j.get('progress',0):.1f}%",'—' if j.get('co') is None else f"{j['co']:.4g}",fmt(j.get('elapsed')),fmt(j.get('eta')),tr('PASS') if j.get('quality',{}).get('passed') else '—']
                for col,v in enumerate(values):
                    item=QTableWidgetItem(v)
                    if j['state']=='FAILED': item.setForeground(QColor('#ba3030'))
                    elif j['state']=='DONE': item.setForeground(QColor('#00795d'))
                    self.jobtable.setItem(i,col,item)
            if row>=0: self.jobtable.selectRow(row)
            self.jobtable.blockSignals(False)
            self.job_selected()
            self.guide.refresh(); self.context_update()
            if self.preview_job_id:
                j=next((x for x in jobs if x['id']==self.preview_job_id),None)
                if j and j['state'] in ('DONE','FAILED'):
                    self.preview_job_id=None; self.jobtable.selectRow(next(i for i,x in enumerate(jobs) if x['id']==j['id']))
                    if (Path(j['case'])/'constant'/'polyMesh').exists():
                        try:
                            self.viewer.load(next(Path(j['case']).glob('*.foam'))); self.tabs.setCurrentIndex(1); q=j.get('quality',{}); self.statusBar().showMessage(text('Real preview: ','真实预览：')+str(q)); self.log.appendPlainText(json.dumps(q,indent=2))
                            if not q.get('passed'): self.quality_view('skewness')
                        except Exception as e: self.log.appendPlainText(str(e))
        worker=Worker(self.engine.tick,self); self.workers.append(worker); worker.success.connect(done); worker.error.connect(lambda e:(setattr(self,'polling',False),self.log.appendPlainText(e))); worker.finished.connect(lambda:self.workers.remove(worker)); worker.start()
    def signal(self,action):
        try: j=self.selected_job(); self.task(lambda:self.engine.signal(j,action),lambda x:self.poll())
        except Exception as e: self.error(str(e))
    def cancel(self):
        try: self.engine.cancel(self.selected_job()); self.poll()
        except Exception as e: self.error(str(e))
    def recover(self):
        try: j=self.selected_job(); self.task(lambda:self.engine.resume_saved(j),lambda x:self.poll())
        except Exception as e: self.error(str(e))
    def reorder(self,direction):
        try: self.engine.reorder(self.selected_job(),direction); self.poll()
        except Exception as e: self.error(str(e))
    def job_selected(self):
        try:
            j=self.selected_job(); details=json.dumps({k:j.get(k) for k in ('state','quality','residuals','failure','max_observed_co','validation_note')},indent=2)
            details+='\n\nlog.solver\n'+j.get('log_tail','')+'\n\nlog.checkMesh\n'+j.get('check_tail',''); self.log.setPlainText(details)
        except ValueError: pass
        if hasattr(self,'workspace_properties'): self.workspace_properties.refresh_results()
        if hasattr(self,'fft_action'): self.context_update()
    def open_job(self,default_field=None):
        try:
            from .post import Result
            j=self.selected_job(); path=next(Path(j['case']).glob('*.foam'))
            def done(result):
                self.viewer.set_result(result)
                if isinstance(default_field,str): self.viewer.field.setCurrentIndex(self.viewer.field.findData(default_field))
                self.tabs.setCurrentIndex(1); self.context_update()
            self.task(lambda:Result(path),done)
        except Exception as e: self.error(str(e))
    def folder_job(self):
        try: os.startfile(self.selected_job()['case'])
        except Exception as e: self.error(str(e))
    def run_folder(self):
        from .models import host_path
        try: os.startfile(str(host_path(self.profile,self.profile.run_dir)))
        except Exception as e: self.error(str(e))
    def import_foam(self):
        path,_=QFileDialog.getOpenFileName(self,'Import reconstructed OpenFOAM case',self.profile.run_dir,'OpenFOAM (*.foam)')
        if path:
            from .post import Result
            self.task(lambda:Result(path),lambda result:(self.viewer.set_result(result),self.tabs.setCurrentIndex(1),self.context_update()))
    def quality_view(self,metric):
        try:
            j=self.selected_job()
            self.task(lambda:audit(j['case']),lambda a:(self.viewer.show_quality(a,metric),self.tabs.setCurrentIndex(1),self.log.setPlainText(json.dumps(a[0],indent=2))))
        except Exception as e: self.error(str(e))
    def dictionaries(self):
        try:
            j=self.selected_job()
            def editable(): return next(x for x in self.engine.store.all() if x['id']==j['id'])['state'] in ('DONE','FAILED','CANCELLED')
            DictionaryDialog(j['case'],editable,self).exec()
        except Exception as e: self.error(str(e))
    def export_path(self,title,ext): return QFileDialog.getSaveFileName(self,title,str(BASE/'exports'/('result.'+ext)),ext.upper()+f' (*.{ext})')[0]
    def png(self):
        path=self.export_path('Save displayed mesh / flow image','png')
        if path: Path(path).parent.mkdir(parents=True,exist_ok=True); self.viewer.image().save(path)
    def gif(self):
        path=self.export_path('Animate genuine saved CFD frames','gif')
        if path:
            try:
                self.activity.show(); self.statusBar().showMessage(text('Rendering genuine GIF frames…','正在渲染真实 GIF 帧…')); Path(path).parent.mkdir(parents=True,exist_ok=True); self.viewer.gif(path)
            except Exception as e: self.error(str(e))
            finally: self.activity.setVisible(self.busy_tasks>0); self.statusBar().showMessage(text('GIF operation finished.','GIF 操作结束。'),5000)
    def csv(self):
        if not self.viewer.result: return self.error('Load a CFD result first.')
        names=list(self.viewer.result.columns()); dlg=Properties('CSV columns / row stride',{'columns':','.join(names),'row_stride':1,'times':'current'},self,{'times':['current','all']})
        if dlg.exec():
            path=self.export_path('Save actual CFD CSV','csv'); vals=dlg.values()
            if path:
                from .post import Result
                foam=self.viewer.result.foam; index=self.viewer.result.index; Path(path).parent.mkdir(parents=True,exist_ok=True)
                def export():
                    result=Result(foam); result.select(index); result.csv(path,[x.strip() for x in vals['columns'].split(',')],vals['row_stride'],vals['times']=='all'); return 'CSV saved / 已保存: '+path
                self.task(export)
    def mat(self):
        if not self.viewer.result: return self.error('Load a CFD result first.')
        path=self.export_path('Save PINN fields / true time values','mat')
        if path:
            from .post import Result
            foam=self.viewer.result.foam; Path(path).parent.mkdir(parents=True,exist_ok=True)
            def export(): Result(foam).mat(path); return 'MAT saved / 已保存: '+path
            self.task(export)
    def force_plot(self):
        try:
            from .spectra import force_dialog
            force_dialog(self.selected_job()['case'],self)
        except Exception as e: self.error(str(e))
    def manual(self,lang): QDesktopServices.openUrl(QUrl.fromLocalFile(str(BASE/'docs'/f'manual_{lang}.html')))
    def closeEvent(self,event):
        if hasattr(self,'terminal') and self.terminal.process.state()!=self.terminal.process.NotRunning:
            QMessageBox.information(self,'WSL Terminal','Exit the terminal shell before closing / 请先在终端输入 exit。'); event.ignore(); return
        if hasattr(self,'ssh_dialog') and (self.ssh_dialog.pending or getattr(self.ssh_dialog,'worker',None) is not None): QMessageBox.information(self,tr('Working'),text('Wait for the active SSH operation before exiting.','退出前请等待当前 SSH 操作完成。')); event.ignore(); return
        if self.workers: QMessageBox.information(self,'Working','Wait for active GUI operations to finish.'); event.ignore(); return
        i18n.save_preference('workspace_tab_area','top' if self.toolBarArea(self.stage_toolbar)==Qt.TopToolBarArea else 'bottom')
        # Solver drivers are detached; the optional headless worker carries queued work.
        if any(j['state']=='QUEUED' for j in self.jobs):
            subprocess.Popen([sys.executable,str(BASE/'app.py'),'--worker'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.viewer.play_timer.stop(); self.viewer.renderer.RemoveAllViewProps(); self.viewer.widget.Finalize()
        self.canvas.scene().blockSignals(True)
        self.design3d.finalize()
        event.accept()

    def typical_flows(self):
        from .quickstart import TemplateDialog
        from .templates import make_template
        dlg=TemplateDialog(self)
        if dlg.exec():
            from .backend import DATA
            folder=DATA/'recovery'; folder.mkdir(exist_ok=True)
            (folder/('before_template_'+str(time.time_ns())+'.json')).write_text(json.dumps(asdict(self.project),indent=2,ensure_ascii=False),encoding='utf-8')
            self.project=make_template(dlg.selection.currentData()); self.canvas.project=self.project; self.canvas.history.clear(); self.canvas.future.clear(); self.canvas.rebuild(); self.canvas.fit(); self.tabs.setCurrentIndex(0); self.pre_mode.setCurrentIndex(0); self.refresh_tree()
    def quick_tutorials(self):
        from .quickstart import Quickstart
        Quickstart(self).exec()
    def source_files(self):
        from .file_browser import FileBrowser
        FileBrowser([(text('Application source (read-only)','软件源码（只读）'),BASE,False)],self).exec()
    def run_files(self):
        from .file_browser import FileBrowser
        from .models import host_path
        self.run_files_dialog=FileBrowser([(text('All OpenFOAM cases (read-only)','全部 OpenFOAM 算例（只读）'),host_path(self.profile,self.profile.run_dir),False)],self)
        self.run_files_dialog.show()
    def case_files(self):
        try:
            from .file_browser import FileBrowser
            j=self.selected_job(); FileBrowser([(text('Actual selected case (read-only)','实际所选算例（只读）'),Path(j['case']),False)],self).exec()
        except Exception as e: self.error(str(e))
    def generated_files(self):
        from .backend import DATA,write_case,prepare_mesh
        from .file_browser import FileBrowser
        p=copy.deepcopy(self.project); draft=DATA/'drafts'/('inputs_'+str(time.time_ns())); draft.parent.mkdir(exist_ok=True)
        def generate():
            write_case(p,self.profile,preview_root=draft); command=prepare_mesh(p,self.profile,draft); (draft/'mesh_command.txt').write_text(command,encoding='utf-8'); return draft
        def done(path):
            roots=[(text('Generated design inputs (draft)','生成设计输入（草稿）'),path,True),(text('Application source (read-only)','软件源码（只读）'),BASE,False)]
            if self.jobtable.currentRow()>=0: roots.append((text('Actual selected case (read-only)','实际所选算例（只读）'),Path(self.selected_job()['case']),False))
            def save(key,content):
                if asdict(self.project)!=asdict(p): raise ValueError('Design changed while drafting; regenerate current inputs first.')
                candidate=copy.deepcopy(self.project); candidate.dictionary_overrides[key]=content; candidate.validate(); self.project.dictionary_overrides[key]=content; p.dictionary_overrides[key]=content; self.refresh_tree()
            self.files_dialog=FileBrowser(roots,self,on_save=save); self.files_dialog.show()
        self.task(generate,done)
    def edit_polygon(self,index):
        from .geometry import vertices,polygon
        shape=self.project.shapes[index]; dlg=QDialog(self); dlg.setWindowTitle(text('Exact polygon vertices / metres','多边形精确顶点 / 米')); dlg.resize(550,450); box=QVBoxLayout(dlg); name=QLineEdit(shape['name']); box.addWidget(name); points=QPlainTextEdit('\n'.join(f'{x:.12g}, {y:.12g}' for x,y in vertices(shape))); box.addWidget(points); buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); box.addWidget(buttons)
        if dlg.exec():
            try:
                solid=polygon([[float(v) for v in line.replace(',',' ').split()] for line in points.toPlainText().splitlines() if line.strip()],name.text()); self.canvas.remember(); self.project.shapes[index]=solid; self.canvas.rebuild(); self.refresh_tree()
            except Exception as e: self.error(str(e))

    def open_manual_topology(self):
        self.active_property_route=None
        self.tabs.setCurrentIndex(0); self.pre_mode.setCurrentIndex(2); self.manual_editor.reload(); self.manual_editor.retranslate(); self.design_stack.setCurrentIndex(2); self.context_update(); self.statusBar().showMessage(text('Manual topology: real nodes, segments and region meshes.','手动拓扑：真实节点、边段和区域网格。'),6000)

    def open_workspace_properties(self,route):
        self.active_property_route=route
        if route!='results' and not self.guide_action.isChecked():self.pre_mode.setCurrentIndex(0)
        self.tabs.setCurrentIndex(1 if route=='results' else 0)
        self.inspector_stack.setCurrentIndex(2);self.workspace_properties.reload(route)
        self.inspector_dock.show();self.inspector_dock.raise_();self.workspace_properties.pages.setFocus()
        self.statusBar().showMessage(text('Opened properties: ','已打开属性：')+{'physics':text('Physics / model','物理 / 模型'),'solver':'PIMPLE','results':text('Mesh / fields / export','网格 / 场 / 导出')}[route],5000)
    def open_mesh_properties(self,page,target=None):
        self.active_property_route='mesh'
        self.tabs.setCurrentIndex(0)
        if not self.guide_action.isChecked():self.pre_mode.setCurrentIndex(1)
        self.inspector_stack.setCurrentIndex(1); self.mesh_inspector.reload(page,target); self.inspector_dock.show(); self.inspector_dock.raise_(); self.mesh_inspector.pages.setFocus(); self.statusBar().showMessage(text('Opened mesh properties: ','已打开网格属性：')+text('Generator','生成器') if page=='generator' else text('Opened refinement / spacing settings','已打开加密 / 间距设置'),5000)
    def draw_refinement_region(self):
        self.open_mesh_properties('refinement'); self.design_view.setCurrentIndex(0); self.canvas.set_tool('region'); self.canvas.setFocus(); self.statusBar().showMessage(text('Click two region corners in the sketch.','请在截面图中点击加密区域的两个角点。'),7000)
    def pre_mode_changed(self,index):
        self.canvas.set_tool('select'); self.design_stack.setCurrentIndex(2 if index==2 else self.design_view.currentIndex()); self.design_view.setVisible(index!=2); self.context_update()
        if index==1 and hasattr(self,'mesh_inspector'): self.open_mesh_properties('generator')
