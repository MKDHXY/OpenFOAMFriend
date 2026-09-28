"""Conventional compact workspace tabs alongside the simulation tree."""
from PySide6.QtGui import QShortcut,QKeySequence
from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QTabBar,QToolBar,QApplication
from PySide6.QtCore import Qt,QEvent
from .i18n import text

class StageNavigation(QWidget):
    pages=(0,2,1)
    def __init__(self,window):
        super().__init__(window); self.window=window; row=QHBoxLayout(self); row.setContentsMargins(0,0,0,0); row.setSpacing(18)
        self.bar=QTabBar(); self.bar.setExpanding(False); self.bar.setDrawBase(False); self.bar.setDocumentMode(True); self.bar.setAccessibleName(text('Workspace tabs','工作区选项卡'))
        self.bar.setStyleSheet('QTabBar{background:#e8edf2;} QTabBar::tab{background:#e8edf2;color:#354c62;padding:8px 22px;border-right:1px solid #cad4de;border-bottom:3px solid transparent;font-size:13px;} QTabBar::tab:selected{background:white;color:#145f78;font-weight:600;border-bottom:3px solid #008ba2;} QTabBar::tab:hover:!selected{background:#dce6ee;}')
        for _ in self.pages: self.bar.addTab('')
        row.addWidget(self.bar); self.context=QLabel(); self.context.setStyleSheet('color:#62758a;font-size:12px;'); row.addWidget(self.context); row.addStretch()
        self.bar.currentChanged.connect(lambda i:window.tabs.setCurrentIndex(self.pages[i]))
        self.header=QWidget(); self.header.hide()
        for index,page in enumerate(self.pages):
            shortcut=QShortcut(QKeySequence('Ctrl+'+str(index+1)),window); shortcut.activated.connect(lambda p=page:window.tabs.setCurrentIndex(p))
        self.refresh()
    def refresh(self):
        w=self.window; page=w.tabs.currentIndex(); labels=(text('Pre-processing','前处理'),text('Computation','计算'),text('Post-processing','后处理'))
        self.bar.blockSignals(True)
        for i,label in enumerate(labels):
            self.bar.setTabText(i,label); self.bar.setTabToolTip(i,(text('Geometry / mesh / initial fields','几何 / 网格 / 初始场'),text('Submit / queue / monitor','提交 / 队列 / 监控'),text('Fields / quality / export','场 / 质量 / 导出'))[i]+f' · Ctrl+{i+1}')
        self.bar.setCurrentIndex(self.pages.index(page)); self.bar.blockSignals(False)
        self.context.setText(text('Current: ','当前：')+labels[self.pages.index(page)])

class DockableStageToolBar(QToolBar):
    """Handle-only drag between horizontal areas; never tears into a floating window."""
    def __init__(self,window):
        super().__init__('Workspace tabs',window); self.window=window; self.drag_start=None
        self.installEventFilter(self)
        self.setToolTip(text('Drag the left grip to the top or bottom. Right-click for docking commands.','拖动左侧手柄到上方或下方；右键也可选择停靠位置。'))
    def eventFilter(self,watched,event):
        # Qt's private movable-toolbar handler may consume grip events before
        # mousePressEvent after re-docking. Own the grip sequence consistently.
        if watched is self:
            if event.type()==QEvent.MouseButtonPress and event.button()==Qt.LeftButton and event.position().x()<=12:
                self.mousePressEvent(event);return True
            if self.drag_start is not None and event.type()==QEvent.MouseMove:
                self.mouseMoveEvent(event);return True
            if self.drag_start is not None and event.type()==QEvent.MouseButtonRelease:
                self.mouseReleaseEvent(event);return True
        return super().eventFilter(watched,event)
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and event.position().x()<=12:
            self.drag_start=event.globalPosition().toPoint(); self.grabMouse(); event.accept(); return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.drag_start is not None:
            self.setCursor(Qt.SizeVerCursor); self.window.statusBar().showMessage(text('Release in the upper or lower half to dock the tabs; outside the window cancels.','在窗口上半部或下半部松开以停靠选项卡；窗口外松开取消。')); event.accept(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self.drag_start is not None and event.button()==Qt.LeftButton:
            start=self.drag_start; self.drag_start=None; self.releaseMouse(); self.unsetCursor(); point=self.window.mapFromGlobal(event.globalPosition().toPoint())
            if (event.globalPosition().toPoint()-start).manhattanLength()>=QApplication.startDragDistance() and self.window.rect().contains(point):
                self.window.position_stage_tabs(Qt.TopToolBarArea if point.y()<self.window.height()/2 else Qt.BottomToolBarArea)
            self.window.statusBar().clearMessage(); event.accept(); return
        super().mouseReleaseEvent(event)
