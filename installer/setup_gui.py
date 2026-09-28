"""Bilingual setup running on the bundled CPython/Qt, not on system Python."""
import sys,json,os,subprocess,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from install_core import install,environment,run
from PySide6.QtCore import QThread,Signal,Qt
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QLineEdit,QPushButton,QPlainTextEdit,QProgressBar,QFileDialog,QMessageBox

class Task(QThread):
    info=Signal(str);success=Signal(object);failed=Signal(str)
    def __init__(self,fn):super().__init__();self.fn=fn
    def run(self):
        try:self.success.emit(self.fn(self.info.emit))
        except Exception:self.failed.emit(traceback.format_exc())

class Setup(QWidget):
    def __init__(self,bundle):
        super().__init__();self.bundle=Path(bundle);self.metadata=json.loads((self.bundle/'bundle.json').read_text());self.full=self.metadata['mode']=='full';self.tasks=[];self.installed=None
        self.setWindowTitle('Open Foam Friend · Setup / 安装');self.resize(860,640);self.setStyleSheet('QWidget{font:10pt "Segoe UI";color:#203c50;background:#f1f4f7} QLineEdit,QComboBox,QPlainTextEdit{background:white;padding:5px;border:1px solid #bacbd8} QPushButton{background:white;padding:7px;border:1px solid #9db8cb} QPushButton:pressed{background:#bedcea}')
        box=QVBoxLayout(self);row=QHBoxLayout();self.title=QLabel();self.title.setStyleSheet('font-size:20px;font-weight:600');row.addWidget(self.title);row.addStretch();row.addWidget(QLabel('Language / 语言'));self.language=QComboBox();self.language.addItems(['中文','English']);self.language.currentIndexChanged.connect(self.translate);row.addWidget(self.language);box.addLayout(row)
        self.note=QLabel();self.note.setWordWrap(True);box.addWidget(self.note);form=QFormLayout();self.target=QLineEdit(str(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'OpenFoamFriend'));self.target_label=QLabel();self.distro_label=QLabel();self.distro=QLineEdit('OpenFoamFriend-14');form.addRow(self.target_label,self.target);form.addRow(self.distro_label,self.distro);box.addLayout(form)
        self.windows=QPushButton();self.windows.clicked.connect(self.windows_stage);self.windows.setVisible(self.full);box.addWidget(self.windows)
        self.install_button=QPushButton();self.install_button.clicked.connect(self.install_stage);box.addWidget(self.install_button)
        buttons=QHBoxLayout();self.check=QPushButton();self.check.clicked.connect(lambda:self.start(lambda progress:environment(),self.report));buttons.addWidget(self.check);self.start_button=QPushButton();self.start_button.setEnabled(False);self.start_button.clicked.connect(self.open_app);buttons.addWidget(self.start_button);self.docs=QPushButton();self.docs.clicked.connect(lambda:os.startfile(self.bundle/'docs'/('installation_ZH.html' if self.language.currentIndex()==0 else 'installation_EN.html')));buttons.addWidget(self.docs);box.addLayout(buttons)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.hide();box.addWidget(self.progress);self.log=QPlainTextEdit();self.log.setReadOnly(True);box.addWidget(self.log,1);self.translate()
    def t(self,en,zh):return zh if self.language.currentIndex()==0 else en
    def translate(self):
        self.title.setText('Open Foam Friend · '+('Full' if self.full else 'Lite'))
        self.note.setText(self.t('Bundled Python, Qt, VTK and Gmsh. '+('1: Prepare Windows (admin, restart if required). 2: Install software and the prepared OpenFOAM 14 image as the current user. Save work before any manual restart.' if self.full else 'Software-only installation. Missing WSL/OpenFOAM is reported, never installed. You can open the design tools and configure an existing environment later.'),'自带 Python、Qt、VTK、Gmsh。'+('1：准备 Windows（需要管理员权限，按提示手动重启）。2：以当前用户安装软件与预装 OpenFOAM 14 的镜像。重启前自行保存工作。' if self.full else '仅安装软件；缺少 WSL/OpenFOAM 时只报告，绝不安装。可以使用设计工具，稍后配置已有计算环境。')))
        self.target_label.setText(self.t('Installation directory','安装目录'));self.distro_label.setText(self.t('Dedicated Linux name (full only)','专用 Linux 名称（仅完整包）'));self.distro.setEnabled(self.full);self.windows.setText(self.t('1 · Prepare Windows / WSL (administrator)','1 · 准备 Windows / WSL（管理员权限）'));self.install_button.setText(self.t('2 · Install complete software + Linux image' if self.full else 'Install software only','2 · 安装软件与 Linux 镜像' if self.full else '仅安装软件'));self.check.setText(self.t('Read-only environment check','只读环境检查'));self.start_button.setText(self.t('Start Open Foam Friend','启动 Open Foam Friend'));self.docs.setText(self.t('Installation guide','安装说明'))
    def start(self,fn,done):
        if self.tasks:return
        for b in (self.windows,self.install_button,self.check,self.start_button):b.setEnabled(False)
        self.progress.show();task=Task(fn);self.tasks.append(task);task.info.connect(self.log.appendPlainText);task.success.connect(done);task.failed.connect(self.failure)
        def finished():
            self.tasks.remove(task);self.progress.hide()
            for b in (self.windows,self.install_button,self.check):b.setEnabled(True)
            self.start_button.setEnabled(self.installed is not None)
        task.finished.connect(finished);task.start()
    def report(self,r):self.log.appendPlainText(json.dumps(r,indent=2,ensure_ascii=False))
    def failure(self,s):self.log.appendPlainText(s);QMessageBox.warning(self,self.t('Installation needs attention','安装需要处理'),s[-1600:])
    def windows_stage(self):
        if not self.full:return
        def action(progress):
            progress('Windows UAC approval required / 需要 Windows UAC 管理员授权')
            def ps(v):return "'"+str(v).replace("'","''")+"'"
            script=self.bundle/'installer/prepare_windows.ps1';args='-NoProfile -ExecutionPolicy Bypass -File "'+str(script)+'" -Bundle "'+str(self.bundle)+'"'
            executable=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
            command=f'$p=Start-Process {ps(executable)} -Verb RunAs -WindowStyle Hidden -ArgumentList {ps(args)} -Wait -PassThru; Write-Output $p.ExitCode'
            code=run(['powershell.exe','-NoProfile','-Command',command],600)
            if code=='3010':return {'restart_required':True,'message':'Save work, restart manually, then run Setup.cmd again / 保存工作，手动重启后重新打开 Setup.cmd'}
            if code!='0':raise RuntimeError('Windows stage failed / Windows 阶段失败: '+code)
            return {'windows_stage':'DONE','restart_required':False}
        self.start(action,self.report)
    def install_stage(self):
        target=self.target.text();distro=self.distro.text()
        def done(r):self.installed=Path(target);self.report(r)
        self.start(lambda progress:install(self.bundle,target,distro,progress),done)
    def open_app(self):
        if self.installed:os.startfile(self.installed/'Open Foam Friend.cmd')
    def closeEvent(self,event):
        if self.tasks:QMessageBox.information(self,self.t('Operation running','操作进行中'),self.t('Wait for installation to finish. Closing cannot safely cancel WSL import.','请等待操作完成，关闭窗口无法安全取消 WSL 镜像导入。'));event.ignore()
        else:event.accept()

if __name__=='__main__':
    app=QApplication(sys.argv);w=Setup(Path(__file__).resolve().parents[1]);w.show();sys.exit(app.exec())
