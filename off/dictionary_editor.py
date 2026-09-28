"""Grouped, formatted, highlighted real dictionaries with safe inactive saves."""
import re,time,os
from pathlib import Path
from PySide6.QtCore import Qt,QRect,QSize
from PySide6.QtGui import QColor,QFont,QPainter,QSyntaxHighlighter,QTextCharFormat,QTextCursor
from PySide6.QtWidgets import *
from .i18n import tr,text

TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/|\#[^\n]*|[{};()]|[^\s{};()]+',re.S)
def tokens(code): return TOKEN.findall(code)
def format_foam(code):
    out=[]; line=[]; depth=0; parens=0
    def flush():
        if line: out.append('    '*max(0,depth)+' '.join(line)); line.clear()
    previous_end=-1
    for match in TOKEN.finditer(code):
        token=match.group(); contiguous=match.start()==previous_end; previous_end=match.end()
        def add(value):
            # OpenFOAM dictionary keys such as div(phi,U) include parentheses.
            # Keep their original adjacency; token equality alone is insufficient.
            if contiguous and line: line[-1]+=value
            else: line.append(value)
        if token.startswith(('//','/*','#')): flush(); out.append('    '*depth+token); continue
        if token=='{' and parens==0: flush(); out.append('    '*depth+'{'); depth+=1
        elif token=='}' and parens==0: flush(); depth-=1; out.append('    '*max(depth,0)+'}')
        elif token==';' and parens==0:
            if not line and out and out[-1].rstrip().endswith('}'): out[-1]+=';'
            else: add(';'); flush()
        else:
            if token=='(': parens+=1
            elif token==')': parens-=1
            add(token)
    flush(); result='\n'.join(out)+'\n'
    if tokens(result)!=tokens(code): raise ValueError('Formatting changed tokens; refusing to rewrite.')
    return result
def validate_foam(code):
    stack=[]
    for token in tokens(code):
        if token in ('{','('): stack.append(token)
        elif token in ('}',')'):
            if not stack or stack.pop()!=('{' if token=='}' else '('): raise ValueError(text('Unbalanced braces or parentheses.','大括号或圆括号不匹配。'))
    if stack: raise ValueError(text('Unclosed braces or parentheses.','存在未闭合括号。'))
    if 'FoamFile' not in code: raise ValueError('FoamFile header missing.')
    return text('Structure check passed. OpenFOAM remains the authoritative parser.','结构检查通过；最终语法由 OpenFOAM 解析器判定。')
class Highlighter(QSyntaxHighlighter):
    def highlightBlock(self,line):
        for pattern,color,bold in [(r'\b(?:FoamFile|solvers|PIMPLE|boundaryField|dimensions|internalField|functions|blocks|vertices|simulationType|RAS)\b','#146e8b',True),(r'\b(?:[-+]?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)\b','#996021',False),(r'"[^"\n]*"','#9b477a',False),(r'//.*|\#.*','#6d8490',False)]:
            fmt=QTextCharFormat(); fmt.setForeground(QColor(color)); fmt.setFontWeight(QFont.Bold if bold else QFont.Normal)
            for m in re.finditer(pattern,line): self.setFormat(m.start(),m.end()-m.start(),fmt)
class Margin(QWidget):
    def __init__(self,editor): super().__init__(editor); self.editor=editor
    def sizeHint(self): return QSize(self.editor.margin_width(),0)
    def paintEvent(self,event): self.editor.paint_margin(event)
class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__(); self.setFont(QFont('Consolas',11)); self.setLineWrapMode(QPlainTextEdit.NoWrap); self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ')*4); self.margin=Margin(self); self.highlighter=Highlighter(self.document()); self.blockCountChanged.connect(self.update_margin); self.updateRequest.connect(self.scroll_margin); self.update_margin()
    def margin_width(self): return 14+self.fontMetrics().horizontalAdvance('9')*len(str(max(1,self.blockCount())))
    def update_margin(self,*args): self.setViewportMargins(self.margin_width(),0,0,0)
    def scroll_margin(self,rect,dy):
        if dy: self.margin.scroll(0,dy)
        else: self.margin.update(0,rect.y(),self.margin.width(),rect.height())
    def resizeEvent(self,event):
        super().resizeEvent(event); r=self.contentsRect(); self.margin.setGeometry(QRect(r.left(),r.top(),self.margin_width(),r.height()))
    def paint_margin(self,event):
        p=QPainter(self.margin); p.fillRect(event.rect(),QColor('#edf3f7')); p.setPen(QColor('#748b9b')); block=self.firstVisibleBlock(); number=block.blockNumber(); top=round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top()); bottom=top+round(self.blockBoundingRect(block).height())
        while block.isValid() and top<=event.rect().bottom():
            if block.isVisible() and bottom>=event.rect().top(): p.drawText(0,top,self.margin.width()-6,self.fontMetrics().height(),Qt.AlignRight,str(number+1))
            block=block.next(); top=bottom; bottom=top+round(self.blockBoundingRect(block).height()); number+=1

DESCRIPTIONS={
'nOuterCorrectors':('PIMPLE outer iterations per timestep.','每个时间步的 PIMPLE 外迭代次数。'),
'nCorrectors':('Pressure correction loops.','压力校正循环次数。'),
'nNonOrthogonalCorrectors':('Additional correction loops for non-orthogonal meshes.','非正交网格附加校正次数。'),
'tolerance':('Absolute linear-solver residual tolerance.','线性求解器绝对残差阈值。'),
'relTol':('Relative residual reduction; Final=0 requests absolute tolerance.','相对残差缩减阈值；Final=0 要求达到绝对阈值。'),
'numberOfSubdomains':('MPI subdomains; must match launch core count.','MPI 分区数，须与启动核心数相符。'),
'maxCo':('Courant limit controlling adaptive internal timestep.','控制自适应内部时间步的 Courant 上限。'),
'deltaT':('Initial internal solver timestep in seconds.','初始内部求解步长，单位秒。'),
'maxDeltaT':('Maximum internal timestep, not field-save spacing.','内部步长上限，不是场保存间隔。'),
'writeInterval':('Saved-field spacing depends on writeControl.','场保存间隔，其含义取决于 writeControl。'),
'endTime':('Simulation end time in seconds.','模拟结束时刻，单位秒。'),
'nu':('Kinematic viscosity in m²/s; Re=UD/nu.','运动黏度，单位 m²/s；Re=UD/nu。'),
}
class DictionaryDialog(QDialog):
    def __init__(self,case,editable,parent=None,preferred='system/fvSolution'):
        super().__init__(parent); self.case=Path(case); self.editable=editable; self.current=None; self.loaded=''; self.setWindowTitle(text('OpenFOAM dictionary workbench','OpenFOAM 参数与代码工作台')); self.resize(1250,820)
        layout=QVBoxLayout(self); title=QLabel(text('Actual case files · grouped navigation · token-preserving formatting','真实算例文件 · 分组导航 · 不改变 token 的格式化')); title.setStyleSheet('font-size:19px;font-weight:600'); layout.addWidget(title)
        bar=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText(text('Find text in code…','在代码中查找…')); bar.addWidget(self.search)
        for en,zh,fn in [('Find','查找',self.find_text),('Format','格式化',self.format_current),('Check structure','检查结构',self.check),('Save current file','保存当前文件',self.save_current)]:
            b=QPushButton(text(en,zh)); b.clicked.connect(fn); bar.addWidget(b)
            if en=='Save current file': self.save_button=b
        layout.addLayout(bar); split=QSplitter(); layout.addWidget(split,1); self.tree=QTreeWidget(); self.tree.setHeaderLabels([text('Case files','算例文件')]); self.tree.setMinimumWidth(230); split.addWidget(self.tree)
        centre=QWidget(); box=QVBoxLayout(centre); self.path_label=QLabel(); self.path_label.setWordWrap(True); box.addWidget(self.path_label); self.editor=CodeEditor(); box.addWidget(self.editor,1); split.addWidget(centre)
        self.reference=QTextBrowser(); self.reference.setMaximumWidth(300); split.addWidget(self.reference); split.setSizes([230,760,260]); self.status=QLabel(); self.status.setWordWrap(True); layout.addWidget(self.status)
        for folder in ('system','constant','0'):
            group=QTreeWidgetItem(self.tree,[folder])
            for f in sorted((self.case/folder).iterdir()):
                if f.is_file() and '.bak_' not in f.name and f.stat().st_size<200000:
                    item=QTreeWidgetItem(group,[f.name]); item.setData(0,Qt.UserRole,str(f))
        self.tree.expandAll(); self.tree.currentItemChanged.connect(self.select_file); self.save_button.setEnabled(self.editable()); self.editor.setReadOnly(not self.editable())
        self.status.setText(text('Inactive cases only. Saves create a dated backup; structural checking is not full OpenFOAM validation.','仅允许编辑非活动算例；保存自动创建时间戳备份。结构检查不能替代 OpenFOAM 完整验证。'))
        target=next((g.child(i) for k in range(self.tree.topLevelItemCount()) for g in [self.tree.topLevelItem(k)] for i in range(g.childCount()) if Path(g.child(i).data(0,Qt.UserRole)).relative_to(self.case).as_posix()==preferred),None)
        if target: self.tree.setCurrentItem(target)
    def select_file(self,item,old=None):
        if not item or not item.data(0,Qt.UserRole): return
        if self.current and self.editor.document().isModified():
            answer=QMessageBox.question(self,text('Unsaved code','未保存代码'),text('Discard unsaved edits and open another file?','放弃未保存修改并打开另一个文件？'))
            if answer!=QMessageBox.Yes:
                self.tree.blockSignals(True); self.tree.setCurrentItem(old); self.tree.blockSignals(False); return
        self.current=Path(item.data(0,Qt.UserRole)); self.loaded=self.current.read_text(); self.editor.setPlainText(format_foam(self.loaded)); self.editor.document().setModified(False); self.path_label.setText(str(self.current.relative_to(self.case))); self.update_reference()
    def update_reference(self):
        code=self.editor.toPlainText(); rows=[]
        for key,(en,zh) in DESCRIPTIONS.items():
            values=re.findall(r'\b'+key+r'\s+([^;\n{}]+)',code)
            if values: rows.append(f'<p><b>{key}</b><br><code>{", ".join(values)}</code><br>{text(en,zh)}</p>')
        self.reference.setHtml('<h3>'+text('Parameter reference','参数说明')+'</h3>'+(''.join(rows) or text('OpenFOAM names remain unchanged. Edit physical settings through the workflow panel before submission.','OpenFOAM 关键字保持原文；提交前优先在流程参数面板设置物理量。')))
    def find_text(self):
        if not self.editor.find(self.search.text()): self.editor.moveCursor(QTextCursor.Start); self.editor.find(self.search.text())
    def format_current(self):
        try: code=format_foam(self.editor.toPlainText()); self.editor.setPlainText(code); self.editor.document().setModified(code!=format_foam(self.loaded)); self.update_reference()
        except Exception as e: self.status.setText(str(e))
    def check(self):
        try: self.status.setText(validate_foam(self.editor.toPlainText())); self.update_reference(); return True
        except Exception as e: self.status.setText(str(e)); return False
    def save_current(self):
        if not self.current or not self.editable(): self.status.setText(text('This case is active or queued. Editing is locked.','该算例活动中或待提交，已锁定编辑。')); return
        if not self.check(): return
        backup=self.current.with_name(self.current.name+'.bak_'+time.strftime('%Y%m%d_%H%M%S')); backup.write_bytes(self.current.read_bytes()); tmp=self.current.with_name(self.current.name+'.off_tmp'); tmp.write_text(self.editor.toPlainText(),encoding='utf-8'); os.replace(tmp,self.current); self.loaded=self.current.read_text(); self.editor.document().setModified(False); self.status.setText(text('Saved with backup: ','已保存，备份：')+backup.name)
    def closeEvent(self,event):
        if self.editor.document().isModified() and QMessageBox.question(self,text('Unsaved edits','未保存修改'),text('Close and discard unsaved code?','关闭并放弃未保存代码？'))!=QMessageBox.Yes: event.ignore()
        else: event.accept()
