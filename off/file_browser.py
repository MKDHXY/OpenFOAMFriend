"""Native file browser for reproducible drafts, real cases and application source."""
from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QSplitter,QTreeView,QFileSystemModel,QMessageBox
from PySide6.QtCore import Qt,QDir,QUrl
from PySide6.QtGui import QDesktopServices
from .dictionary_editor import CodeEditor,validate_foam
from .physics import EDITABLE_KEYS
from .i18n import text

class FileBrowser(QDialog):
    def __init__(self,roots,parent=None,on_save=None):
        super().__init__(parent); self.setWindowTitle(text('Generated case files / application source','生成算例文件 / 软件源码')); self.resize(1120,750); self.roots=roots; self.on_save=on_save; self.current=None
        box=QVBoxLayout(self); row=QHBoxLayout(); self.scope=QComboBox()
        for label,path,editable in roots: self.scope.addItem(label)
        row.addWidget(self.scope,1); folder=QPushButton(text('Open folder','打开文件夹')); folder.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.root)))); row.addWidget(folder); box.addLayout(row)
        self.note=QLabel(); self.note.setWordWrap(True); box.addWidget(self.note); split=QSplitter(); box.addWidget(split,1); self.tree=QTreeView(); self.tree.setMinimumWidth(280); split.addWidget(self.tree); self.editor=CodeEditor(); self.editor.setReadOnly(True); split.addWidget(self.editor); split.setSizes([350,770]); self.model=QFileSystemModel(self); self.model.setFilter(QDir.AllEntries|QDir.NoDotAndDotDot); self.tree.setModel(self.model)
        self.tree.setColumnHidden(2,True); self.tree.setColumnHidden(3,True); self.tree.setColumnWidth(0,260); self.tree.clicked.connect(self.open_index)
        row=QHBoxLayout(); self.path_label=QLabel(); self.path_label.setWordWrap(True); row.addWidget(self.path_label,1); self.save_button=QPushButton(text('Save draft & apply dictionary override','保存草稿并应用字典覆盖')); self.save_button.clicked.connect(self.save); row.addWidget(self.save_button); box.addLayout(row)
        self.scope.currentIndexChanged.connect(self.choose_root); self.choose_root(0)
    def choose_root(self,index):
        label,path,self.editable=self.roots[index]; self.root=Path(path); self.current=None; self.model.setRootPath(str(self.root)); self.tree.setRootIndex(self.model.index(str(self.root))); self.editor.setPlainText(''); self.editor.setReadOnly(True); self.save_button.setEnabled(False)
        self.note.setText(text('Draft: generated inputs, not yet a checked mesh or solved fields. Actual case: read-only, including polyMesh/logs/time fields. Source: read-only. Select any file. Only draft dictionary edits are applied to this project; use Generate/check to verify them.','草稿：已生成输入，尚非检查后的网格或求解场。实际算例：只读，可见 polyMesh、日志与时间场。软件源码：只读。选择文件即可查看；仅草稿字典编辑应用到项目，须再生成/检查。'))
    def open_index(self,index): self.open_file(Path(self.model.filePath(index)))
    def open_file(self,path):
        if not path.is_file(): return
        self.current=path; self.path_label.setText(str(path)); size=path.stat().st_size; data=path.read_bytes() if size<=2_000_000 else b''; rel=path.relative_to(self.root).as_posix()
        is_text=size<=2_000_000 and b'\0' not in data[:4096]
        self.editor.setPlainText(data.decode('utf-8',errors='replace') if is_text else text(f'Binary or large file: {size:,} bytes. Open its folder for external inspection.',f'二进制或大文件：{size:,} 字节。请打开文件夹用外部软件查看。'))
        allow=self.editable and rel in EDITABLE_KEYS and is_text; self.editor.setReadOnly(not allow); self.save_button.setEnabled(allow)
    def save(self):
        if not self.current or not self.editable or not self.save_button.isEnabled(): return
        try:
            content=self.editor.toPlainText(); validate_foam(content); rel=self.current.relative_to(self.root).as_posix()
            if self.on_save: self.on_save(rel,content)
            self.current.write_text(content,encoding='utf-8'); self.note.setText(text('Saved and applied explicit project override. Regenerate/check before solving.','已保存并应用为明确项目覆盖；求解前须重新生成并检查。'))
        except Exception as e: QMessageBox.warning(self,text('Invalid dictionary','字典无效'),str(e))
