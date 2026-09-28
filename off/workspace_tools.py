"""WSL discovery, reusable command console, editable design and case export."""
import json,os,re,shlex,shutil,subprocess
from pathlib import Path
from dataclasses import asdict
from PySide6.QtCore import QProcess,Qt
from PySide6.QtWidgets import *
from .models import Project,Profile
from .dictionary_editor import CodeEditor,format_foam
from .i18n import text

def discover_wsl():
    """Inspect installed distributions; no machine-specific guessed user path."""
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    raw=subprocess.run(['wsl','--list','--quiet'],capture_output=True,timeout=20,creationflags=flags)
    if raw.returncode: raise RuntimeError(raw.stderr.decode('utf-8',errors='replace'))
    decoded=raw.stdout.decode('utf-16-le' if b'\0' in raw.stdout else 'utf-8',errors='replace')
    script="import glob,json,os,pwd; u=pwd.getpwuid(os.getuid()).pw_name; home=os.path.expanduser('~'); files=sorted(set(glob.glob('/opt/openfoam*/etc/bashrc')+glob.glob('/usr/lib/openfoam/*/etc/bashrc')+glob.glob(home+'/OpenFOAM/*/etc/bashrc'))); print(json.dumps({'user':u,'home':home,'cores':os.cpu_count(),'bashrcs':files,'runs':sorted(glob.glob(home+'/OpenFOAM/*/run'))}))"
    records=[]
    for distro in decoded.replace('\0','').splitlines():
        distro=distro.strip()
        if not distro: continue
        try:
            p=subprocess.run(['wsl','-d',distro,'--','python3','-c',script],capture_output=True,text=True,timeout=30,creationflags=flags)
            if p.returncode: records.append({'distro':distro,'error':p.stderr.strip()}); continue
            records.append(dict(distro=distro,**json.loads(p.stdout)))
        except Exception as e: records.append({'distro':distro,'error':str(e)})
    return records

class CommandLine(QLineEdit):
    def __init__(self,parent=None): super().__init__(parent); self.history=[]; self.history_index=0
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Up,Qt.Key_Down) and self.history:
            self.history_index=max(0,min(len(self.history),self.history_index+(-1 if event.key()==Qt.Key_Up else 1))); self.setText(self.history[self.history_index] if self.history_index<len(self.history) else ''); return
        super().keyPressEvent(event)

class Terminal(QWidget):
    """Persistent WSL Bash console. Plain text streams, not a full VT emulator."""
    def __init__(self,profile,parent=None):
        super().__init__(parent); self.profile=profile; self.process=QProcess(self); self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.receive); self.process.started.connect(lambda:self.output.appendPlainText('WSL shell connected / WSL 已连接')); self.process.errorOccurred.connect(lambda error:self.output.appendPlainText(self.process.errorString())); self.process.finished.connect(lambda code,status:self.output.appendPlainText(f'Exit / 退出: {code}'))
        box=QVBoxLayout(self); row=QHBoxLayout(); self.path=QLineEdit(profile.run_dir); row.addWidget(QLabel('Working directory / 工作目录')); row.addWidget(self.path)
        start=QPushButton('Connect / 连接'); start.clicked.connect(self.start); row.addWidget(start); interrupt=QPushButton('Ctrl+C'); interrupt.clicked.connect(lambda:self.process.write(b'\x03')); row.addWidget(interrupt); stop=QPushButton('Exit / 退出'); stop.clicked.connect(lambda:self.process.write(b'exit\n')); row.addWidget(stop); box.addLayout(row)
        self.output=QPlainTextEdit(); self.output.setReadOnly(True); self.output.setMaximumBlockCount(10000); self.output.setStyleSheet('font-family:Consolas;background:#18232d;color:#e4edf5;'); box.addWidget(self.output)
        self.command=CommandLine(); self.command.setPlaceholderText('Bash / OpenFOAM command · Enter to send · ↑ history'); self.command.returnPressed.connect(self.send); box.addWidget(self.command)
    def start(self):
        if self.process.state()!=QProcess.NotRunning: return
        if not self.path.text().startswith('/'): self.output.appendPlainText('Absolute Linux working directory required.'); return
        # Linux PTY handles interactive Bash and Ctrl+C; Qt keeps the UI responsive.
        code="import os,pty; os.chdir("+repr(self.path.text())+"); pty.spawn(['bash','--noprofile','--rcfile',"+repr(self.profile.bashrc)+",'-i'])"
        self.process.start('wsl',['-d',self.profile.distro,'--','python3','-u','-c',code])
        self.output.appendPlainText('Connecting / 正在连接…')
    def send(self):
        if self.process.state()!=QProcess.Running: self.output.appendPlainText('Connect the shell first / 请先连接'); return
        command=self.command.text(); self.command.history.append(command); self.command.history_index=len(self.command.history); self.command.clear(); self.process.write((command+'\n').encode('utf-8'))
    def receive(self):
        data=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace'); data=re.sub(r'\x1b\][^\x07]*\x07|\x1b\[[0-?]*[ -/]*[@-~]','',data)
        cursor=self.output.textCursor(); cursor.movePosition(cursor.MoveOperation.End); cursor.insertText(data.replace('\r','')); self.output.setTextCursor(cursor); self.output.ensureCursorVisible()

class DesignCodeDialog(QDialog):
    def __init__(self,project,parent=None):
        super().__init__(parent); self.result_project=None; self.setWindowTitle('Preprocessing parameters & generated mesh code / 前处理参数与网格代码'); self.resize(960,700); box=QVBoxLayout(self); tabs=QTabWidget(); box.addWidget(tabs)
        self.editor=CodeEditor(); self.editor.setPlainText(json.dumps(asdict(project),indent=2,ensure_ascii=False)); tabs.addTab(self.editor,'Editable project / 可编辑项目')
        from .mesh import cylinder_dict,partitioned_box_dict
        if project.mesh_method.startswith('Structured'):
            source=project.dictionary_overrides.get('system/blockMeshDict') or (cylinder_dict(project) if project.mesh_method=='Structured cylinder O-grid' else partitioned_box_dict(project))
        else:
            source='Gmsh generator: off/mesh.py → build_gmsh\n'+Path(__file__).with_name('mesh.py').read_text(encoding='utf-8')
        generated=CodeEditor(); generated.setPlainText(format_foam(source) if project.mesh_method.startswith('Structured') else source); generated.setReadOnly(True); tabs.addTab(generated,'Generated mesh source / 网格生成源代码')
        box.addWidget(QLabel(text('SI: lengths m; U m/s; nu m²/s; times s; p m²/s². Project edits are validated before Apply. Generated source follows project parameters; initial dictionaries have their separate editor. Lines are construction guides, not solid boundaries.','SI：长度 m；速度 m/s；ν m²/s；时间 s；p m²/s²。应用前验证项目参数。生成代码由参数驱动；初始文件有独立编辑器。直线为构造线，并非实体边界。')))
        buttons=QDialogButtonBox(QDialogButtonBox.Apply|QDialogButtonBox.Cancel); buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply); buttons.rejected.connect(self.reject); box.addWidget(buttons)
    def apply(self):
        try: project=Project(**json.loads(self.editor.toPlainText())); project.validate(); self.result_project=project; self.accept()
        except Exception as e: QMessageBox.warning(self,'Invalid project / 项目无效',str(e))

def export_case(foam,destination):
    """Copy a complete SERIAL case without overwriting any destination."""
    foam=Path(foam); source=foam.parent; target=Path(destination)
    if target.exists(): raise FileExistsError('Choose a new folder; existing exports are protected.')
    times=sorted((p for p in source.iterdir() if p.is_dir() and re.fullmatch(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?',p.name)),key=lambda p:float(p.name))
    if not (source/'constant/polyMesh/points').exists() or not times: raise ValueError('Reconstructed serial mesh and genuine fields required.')
    if not any((p/'U').exists() and (p/'p').exists() for p in times): raise ValueError('No genuine serial U,p fields; reconstruct first.')
    target.mkdir(parents=True)
    try:
        for name in ['system','constant','postProcessing']:
            if (source/name).is_dir(): shutil.copytree(source/name,target/name)
        if (source/'off_native').is_dir(): shutil.copytree(source/'off_native',target/'off_native',ignore=shutil.ignore_patterns('lnInclude','linux64*'))
        for folder in times: shutil.copytree(folder,target/folder.name)
        for logfile in source.glob('log.*'): shutil.copy2(logfile,target/logfile.name)
        for name in ('off_project.json','mesh_backend.json','mesh_generator_source.py','geometry.msh','geometry.brep'):
            if (source/name).is_file(): shutil.copy2(source/name,target/name)
        marker=target/(target.name+'.foam'); marker.touch()
        metadata={'source':str(foam),'field_times_s':[float(p.name) for p in times if (p/'U').exists() and (p/'p').exists()],'complete':True,'marker':str(marker),'native_model_sources':(target/'off_native').exists(),'native_note':'If off_native exists, source the same Foundation 14 installation and run wmake libso off_native/dynamicLagrangian before solving on a different host.'}; (target/'export_manifest.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8'); return metadata
    except Exception:
        (target/'EXPORT_INCOMPLETE.txt').write_text('Interrupted export. Do not use as verified data.'); raise
