"""Independent manual-mesh drafting workbench: nodes, curves, faces, assignment."""
import copy,math,json
from PySide6.QtCore import Qt,QPointF,QRectF,Signal
from PySide6.QtGui import QPen,QBrush,QColor,QPainterPath,QPainter,QAction,QActionGroup,QPolygonF
from PySide6.QtWidgets import *
from .numeric_controls import ScientificSpin
from .i18n import text
from . import manual_topology as topo

class TopologyView(QGraphicsView):
    position=Signal(str)
    def __init__(self,editor):
        scene=QGraphicsScene(editor); super().__init__(scene); self.graph_scene=scene; self.editor=editor; self.setRenderHint(QPainter.Antialiasing); self.setMouseTracking(True); self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.tool='select'; self.draft=[]; self.ortho=False; self.setMinimumWidth(420); self.setFocusPolicy(Qt.StrongFocus)
    def xy(self,pos):
        v=self.mapToScene(pos); x,y=v.x(),-v.y(); spacing=self.editor.grid.value()
        if self.editor.grid_snap.isChecked():x,y=round(x/spacing)*spacing,round(y/spacing)*spacing
        if self.editor.node_snap.isChecked():
            tol=9/self.transform().m11()
            near=min(self.editor.graph['nodes'].values(),key=lambda v:math.dist(v,(x,y)),default=None)
            if near is not None and math.dist(near,(x,y))<tol:x,y=near
            elif self.editor.reference_snap.isChecked():
                from .manual_reference import points
                near=min(points(self.editor.window.project),key=lambda v:math.dist(v,(x,y)),default=None)
                if near is not None and math.dist(near,(x,y))<tol:x,y=near
        if self.ortho and self.draft:
            a,b=self.draft[0]
            if abs(x-a)>abs(y-b):y=b
            else:x=a
        return x,y
    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        if 1e-5<self.transform().m11()*factor<1e9:self.scale(factor,factor)
        self.editor.redraw(); self.viewport().update(); event.accept()
    def drawBackground(self,painter,rect):
        painter.fillRect(rect,QColor('#fafcfe')); step=self.editor.grid.value(); pixel=step*self.transform().m11()
        while pixel<20:step*=10; pixel*=10
        if rect.width()/step>500 or rect.height()/step>500:return
        painter.setPen(QPen(QColor('#e1e7ee'),0))
        for k in range(math.floor(rect.left()/step),math.ceil(rect.right()/step)+1):painter.drawLine(QPointF(k*step,rect.top()),QPointF(k*step,rect.bottom()))
        for k in range(math.floor(rect.top()/step),math.ceil(rect.bottom()/step)+1):painter.drawLine(QPointF(rect.left(),k*step),QPointF(rect.right(),k*step))
    def drawForeground(self,painter,rect):
        painter.save(); painter.resetTransform(); painter.fillRect(0,0,self.viewport().width(),23,QColor('#e7edf3')); painter.fillRect(0,0,58,self.viewport().height(),QColor('#e7edf3')); painter.setPen(QColor('#294660'))
        for px in range(110,self.viewport().width(),100):painter.drawText(px,17,f'{self.mapToScene(px,0).x():.4g}')
        for py in range(60,self.viewport().height(),90):painter.drawText(3,py,f'{-self.mapToScene(0,py).y():.4g}')
        painter.drawText(5,17,'m'); painter.restore()
    def choose(self,tool):
        self.tool=tool; self.draft=[]; self.setDragMode(QGraphicsView.NoDrag); self.setCursor(Qt.ArrowCursor if tool=='select' else Qt.CrossCursor); self.editor.hint.setText(self.editor.tool_hint(tool))
    def nearest_edge(self,xy):
        candidates=[(topo.projection(self.editor.graph,e,xy)[2],e['id']) for e in self.editor.graph['edges']]
        if not candidates:return None
        dist,eid=min(candidates);return eid if dist<10/self.transform().m11() else None
    def mousePressEvent(self,event):
        if event.button()==Qt.MiddleButton:self.pan_start=event.position().toPoint(); self.setCursor(Qt.ClosedHandCursor); event.accept();return
        if event.button()==Qt.RightButton:self.draft=[]; self.editor.redraw(); event.accept();return
        if event.button()!=Qt.LeftButton:return super().mousePressEvent(event)
        xy=self.xy(event.position().toPoint()); ed=self.editor
        try:
            if self.tool=='select':
                item=self.itemAt(event.position().toPoint())
                while item and item.data(0) is None:item=item.parentItem()
                ed.select(item.data(0) if item else None); return
            if self.tool=='node':ed.mutate(lambda g:topo.add_node(g,xy));return
            if self.tool in ('split','erase'):
                eid=self.nearest_edge(xy)
                if eid is None:ed.message(text('Click a curve segment.','请点击一段曲线。'),True);return
                ed.mutate(lambda g:topo.split(g,eid,xy) if self.tool=='split' else topo.erase(g,eid));return
            self.draft.append(xy); needed=3 if self.tool=='arc' else 2
            if len(self.draft)==needed:
                pts=self.draft[:]
                def make(g):
                    if self.tool=='rectangle':
                        a,b=pts[0],pts[-1]
                        if abs(a[0]-b[0])<1e-9 or abs(a[1]-b[1])<1e-9:raise ValueError('Rectangle needs finite width and height / 矩形须有宽度和高度。')
                        ns=[topo.add_node(g,v) for v in [(min(a[0],b[0]),min(a[1],b[1])),(max(a[0],b[0]),min(a[1],b[1])),(max(a[0],b[0]),max(a[1],b[1])),(min(a[0],b[0]),max(a[1],b[1]))]]
                        for i in range(4):topo.add_edge(g,ns[i],ns[(i+1)%4])
                    elif self.tool=='circle':
                        x,y=pts[0];r=math.dist(pts[0],pts[1])
                        if r<1e-9:raise ValueError('Positive circle radius required / 圆半径须大于零。')
                        ns=[topo.add_node(g,(x+r*math.cos(i*math.pi/2),y+r*math.sin(i*math.pi/2))) for i in range(4)]
                        for i in range(4):topo.add_edge(g,ns[i],ns[(i+1)%4],(x+r*math.cos((i+.5)*math.pi/2),y+r*math.sin((i+.5)*math.pi/2)))
                    else:
                        a=topo.add_node(g,pts[0]); b=topo.add_node(g,pts[-1]); topo.add_edge(g,a,b,pts[1] if self.tool=='arc' else None)
                ed.mutate(make); self.draft=[pts[-1]] if self.tool=='polyline' else []
            ed.redraw()
        except Exception as e:ed.message(str(e),True);self.draft=[]
        event.accept()
    def mouseMoveEvent(self,event):
        if getattr(self,'pan_start',None) is not None:
            pos=event.position().toPoint(); diff=pos-self.pan_start; self.pan_start=pos; self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-diff.x()); self.verticalScrollBar().setValue(self.verticalScrollBar().value()-diff.y()); event.accept();return
        xy=self.xy(event.position().toPoint()); self.position.emit(f'x={xy[0]:.8g} m; y={xy[1]:.8g} m')
        if self.draft:self.editor.redraw(preview=xy)
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MiddleButton:self.pan_start=None; self.setCursor(Qt.ArrowCursor if self.tool=='select' else Qt.CrossCursor);return
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape:self.draft=[];self.editor.redraw();return
        if event.key()==Qt.Key_F8:self.ortho=not self.ortho;self.editor.message(text('Orthogonal constraint: ','正交绘制约束：')+str(self.ortho));return
        if event.key()==Qt.Key_Delete and self.editor.selected and self.editor.selected[0]=='edge':self.editor.mutate(lambda g:topo.erase(g,self.editor.selected[1]));return
        if event.modifiers()&Qt.ControlModifier and event.key()==Qt.Key_Z:self.editor.undo();return
        if event.modifiers()&Qt.ControlModifier and event.key()==Qt.Key_Y:self.editor.redo();return
        super().keyPressEvent(event)

class ManualEditor(QWidget):
    def __init__(self,window):
        super().__init__(); self.window=window; self.graph=topo.empty(); self.project_ref=None; self.history=[]; self.future=[]; self.selected=None; self.busy=False
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); toolbar=QToolBar(); toolbar.setStyleSheet('QToolBar{background:#e5edf4;padding:2px} QToolButton{color:#173b5d;padding:5px} QToolButton:checked{background:white;border-bottom:2px solid #008eaa}'); layout.addWidget(toolbar); self.actions={}; group=QActionGroup(self); group.setExclusive(True)
        for key,en,zh in [('select','Select','选择'),('node','Node','节点'),('line','Line','直线'),('polyline','Polyline','连续折线'),('arc','3-point arc','三点圆弧'),('circle','Circle','圆'),('rectangle','Rectangle','矩形'),('split','Split at point','点处打断'),('erase','Erase segment','擦除线段')]:
            a=toolbar.addAction(text(en,zh));a.setCheckable(True); group.addAction(a); self.actions[key]=(a,en,zh);a.triggered.connect(lambda checked,k=key:self.view.choose(k))
        self.actions['select'][0].setChecked(True); commandbar=QToolBar();commandbar.setStyleSheet(toolbar.styleSheet());layout.addWidget(commandbar)
        self.toolbars=[toolbar,commandbar];self.commands=[]
        for en,zh,fn in [('Undo','撤销',self.undo),('Redo','重做',self.redo),('Fit domain','适配流场',self.fit),('Fit model','适配模型',self.fit_model),('Exact coordinates…','精确坐标…',self.exact),('Cylinder blocks…','圆柱分块…',self.preset),('Validate topology','检查拓扑',self.check)]:
            a=commandbar.addAction(text(en,zh));a.triggered.connect(fn);self.commands.append((a,en,zh))
        self.hint=QLabel(); self.hint.setWordWrap(True);layout.addWidget(self.hint)
        options=QHBoxLayout(); self.backend=QComboBox(); self.backend.addItems(['blockMesh','Gmsh']); options.addWidget(self.backend);self.grid=ScientificSpin();self.grid.setRange(1e-10,1e9);self.grid.setValue(.1);self.grid.setMaximumWidth(120);self.grid_label=QLabel();options.addWidget(self.grid_label);options.addWidget(self.grid);self.grid_snap=QCheckBox();self.node_snap=QCheckBox();self.node_snap.setChecked(True);options.addWidget(self.grid_snap);options.addWidget(self.node_snap);self.reference_label=QLabel();options.addWidget(self.reference_label);self.reference=ScientificSpin();self.reference.setRange(1e-10,1e9);self.reference.setValue(1);self.reference.setMaximumWidth(120);options.addWidget(self.reference);options.addStretch();layout.addLayout(options)
        split=QSplitter(); layout.addWidget(split,1); self.view=TopologyView(self); self.view.position.connect(window.statusBar().showMessage);split.addWidget(self.view)
        props=QWidget();props.setStyleSheet("QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox{padding:2px;} QLabel{padding:0px;}");box=QVBoxLayout(props);self.list=QListWidget(); self.list.setMinimumHeight(75);self.list.setMaximumHeight(100);self.list.currentItemChanged.connect(lambda item,prev:self.select(item.data(Qt.UserRole)) if item and not self.busy else None);box.addWidget(self.list)
        self.form_stack=QStackedWidget();box.addWidget(self.form_stack,1);self.inputs={}; self.labels=[]
        def page(kind,rows):
            container=QScrollArea();container.setWidgetResizable(True);container.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn); body=QWidget();container.setWidget(body);f=QFormLayout(body);f.setVerticalSpacing(3)
            for key,en,zh,typ in rows:
                w=QComboBox() if isinstance(typ,list) else QSpinBox() if typ=='int' else QLineEdit() if typ=='str' else ScientificSpin()
                if isinstance(typ,list):
                    for title,value in typ:w.addItem(title,value)
                elif typ=='int':w.setRange(1,1000000)
                elif typ not in ('str','int'):w.setRange(-1e9 if key in ('x','y','mx','my') else 1e-10,1e9)
                label=QLabel(); label.setWordWrap(True); f.addRow(label,w);self.labels.append((label,en,zh));self.inputs[kind,key]=w
            self.form_stack.addWidget(container)
        page('node',[('x','x / m','x / m','float'),('y','y / m','y / m','float')])
        page('edge',[('count','Cells along E: a → b','沿边单元数 E：a → b','int'),('ratio','h_last / h_first (a → b)','末/首间距比（a → b）','float'),('patch','Boundary patch','边界 patch',[(s,s) for s in ['auto','inlet','outlet','farfield','cylinder','interior']]),('mx','Arc through x / m','圆弧过点 x / m','float'),('my','Arc through y / m','圆弧过点 y / m','float')])
        page('face',[('name','Region name','区域名称','str'),('role','Role','区域用途',[('Fluid / 流体','fluid'),('Hole / 排除区','hole')]),('method','Region mesh','区域网格',[('Mapped quad / 映射四边形','mapped'),('Triangles / 三角形','tri'),('Quad dominant / 四边形主导','quad')]),('nx','N along side 1','边 1 方向单元数','int'),('ny','N along side 2','边 2 方向单元数','int'),('gx','Side 1 h_last/h_first','边 1 末/首间距比','float'),('gy','Side 2 h_last/h_first','边 2 末/首间距比','float'),('size','Target size / m (unstructured)','目标间距 / m（非结构化）','float')])
        self.selection=QLabel();self.selection.setWordWrap(True);box.addWidget(self.selection);self.apply=QPushButton();self.apply.clicked.connect(self.apply_selected);box.addWidget(self.apply);self.activate_button=QPushButton();self.activate_button.clicked.connect(self.activate);box.addWidget(self.activate_button);self.generate=QPushButton();self.generate.clicked.connect(self.generate_mesh);box.addWidget(self.generate);split.addWidget(props);split.setSizes([820,330]); props.setMinimumWidth(275);props.setMaximumWidth(430)
        self.feedback=QLabel();self.feedback.setWordWrap(True); layout.addWidget(self.feedback);self.retranslate();self.reload()
        context=QHBoxLayout();self.context_toggle=QCheckBox();self.context_toggle.setChecked(True);self.reference_snap=QCheckBox();self.reference_snap.setChecked(True);self.import_context=QPushButton();self.import_context.clicked.connect(self.import_reference);self.context_label=QLabel();self.context_label.setWordWrap(True)
        context.addWidget(self.context_toggle);context.addWidget(self.reference_snap);context.addWidget(self.import_context);context.addWidget(self.context_label,1);layout.insertLayout(3,context);self.context_toggle.toggled.connect(lambda _:self.redraw());self.retranslate();self.redraw();self.fit()
    def tool_hint(self,tool):
        return text({'select':'Select a node, edge segment or closed region.','node':'Click to place a topology node.','polyline':'Click consecutive nodes; Esc or right click ends the chain.','circle':'Click centre, then radius point; creates four arc segments.','rectangle':'Click two opposite corners; creates four connected edges.','line':'Click start, then end; shared endpoints snap.','arc':'Click start, through-point, then end.','split':'Click inside a line/arc to insert a node and split the edge.','erase':'Click the exact node-to-node segment to erase it.'}[tool],{'select':'选择节点、两节点间的边或闭合区域。','node':'单击放置拓扑节点。','polyline':'依次点击节点；Esc 或右键结束连续折线。','circle':'点击中心，再点击半径点；产生四段圆弧。','rectangle':'点击两个对角点；产生四条相连边。','line':'依次点击起点、终点；自动吸附共享端点。','arc':'依次点击起点、过点、终点。','split':'在线段/圆弧内部点击，插入节点并打断。','erase':'点击要擦除的两个节点之间的具体线段。'}[tool])+text(' Wheel zoom; middle drag pan; Esc cancels; F8 ortho. Units m.',' 滚轮缩放；中键平移；Esc 取消；F8 正交。单位 m。')
    def retranslate(self):
        if hasattr(self,'context_toggle'):
            self.context_toggle.setText(text('Show model / domain','显示模型 / 流场'));self.reference_snap.setText(text('Reference snap','参考点吸附'));self.import_context.setText(text('Import boundaries','导入模型 / 流场边界'))
            self.import_context.setToolTip(text('Import the rectangular design extent (xmin/xmax/ymin/ymax) and solid holes. Use Cylinder blocks for a circular outer domain. Imported loops are editable and undoable.','导入 xmin/xmax/ymin/ymax 定义的矩形设计流场与实体排除区；圆形外流场请用“圆柱分块”。导入后可编辑、可撤销。'))
            self.context_label.setText(text('Dashed = geometry reference; blue = editable mesh topology. XY section, ','虚线 = 几何参考；蓝线 = 可编辑网格拓扑。XY 截面，')+f'{self.window.project.dimension}D · Z={self.window.project.depth:g} m')
        for a,en,zh in list(self.actions.values())+self.commands:a.setText(text(en,zh))
        for label,en,zh in self.labels:label.setText(text(en,zh))
        for key,choices in [('role',[('Fluid','流体'),('Hole','排除区')]),('method',[('Mapped quad','映射四边形'),('Triangles','三角形'),('Quad dominant','四边形主导')])]:
            combo=self.inputs['face',key]
            for i,(en,zh) in enumerate(choices):combo.setItemText(i,text(en,zh))
        for bar in self.toolbars:
            for button in bar.findChildren(QToolButton):
                if button.defaultAction():button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.defaultAction().text())+22)
            bar.layout().invalidate()
        for checkbox in (self.grid_snap,self.node_snap):checkbox.setMinimumWidth(checkbox.fontMetrics().horizontalAdvance(text('Node snap','节点吸附'))+35)
        self.reference_label.setText(text('Flow Lref / m','流动 Lref / m'));self.grid_label.setText(text('Grid / m','参考网格 / m'));self.grid_snap.setText(text('Grid snap','网格吸附'));self.node_snap.setText(text('Node snap','节点吸附'));self.apply.setText(text('Apply selected object','应用所选对象'));self.activate_button.setText(text('Use this topology for meshing','将此拓扑用于网格'));self.generate.setText(text('Generate / check actual mesh','生成 / 检查真实网格'));self.hint.setText(self.tool_hint(self.view.tool));self.select(self.selected);self.feedback.clear()
    def reload(self):
        if self.project_ref is not self.window.project:
            self.project_ref=self.window.project; self.reference.setValue(self.window.project.reference_length or 1); self.backend.setCurrentIndex(1 if self.window.project.mesh_method==topo.METHODS[1] else 0); self.graph=copy.deepcopy(self.window.project.manual_mesh or topo.empty()); self.history=[];self.future=[];self.selected=None;self.redraw();self.fit()
        elif hasattr(self,'context_toggle'):self.redraw()
    def message(self,value,error=False):self.feedback.setText(value);self.feedback.setStyleSheet('color:#ab302b' if error else 'color:#187657');self.window.statusBar().showMessage(value,7000)
    def mutate(self,fn):
        before=copy.deepcopy(self.graph)
        try:fn(self.graph)
        except Exception:self.graph=before;raise
        self.history.append(before);self.future=[];self.window.project.manual_mesh=copy.deepcopy(self.graph);self.redraw();self.window.refresh_tree();self.message(text('Topology changed; validate and regenerate before solving.','拓扑已修改；求解前须检查并重新生成。'))
    def undo(self):
        if self.view.draft:self.view.draft=[];self.redraw();return
        if self.history:self.future.append(copy.deepcopy(self.graph));self.graph=self.history.pop();self.sync()
    def redo(self):
        if self.future:self.history.append(copy.deepcopy(self.graph));self.graph=self.future.pop();self.sync()
    def sync(self):self.window.project.manual_mesh=copy.deepcopy(self.graph);self.redraw();self.window.refresh_tree()
    def fit(self):
        self.view.fitInView(self.view.sceneRect(),Qt.KeepAspectRatio); self.redraw()
    def fit_model(self):
        p=self.window.project
        if not p.shapes:return self.fit()
        from .geometry import vertices
        pts=[]
        for s in p.shapes:
            pts.extend([(s['x']-s['width']/2,s['y']-s['height']/2),(s['x']+s['width']/2,s['y']+s['height']/2)] if s['kind']=='circle' else vertices(s))
        xs=[v[0] for v in pts];ys=[v[1] for v in pts];margin=max(max(xs)-min(xs),max(ys)-min(ys),1e-9)*.6
        self.view.fitInView(QRectF(min(xs)-margin,-max(ys)-margin,max(xs)-min(xs)+2*margin,max(ys)-min(ys)+2*margin),Qt.KeepAspectRatio);self.redraw()
    def redraw(self,preview=None):
        self.busy=True;scene=self.view.scene();scene.clear();g=self.graph;fs=topo.faces(g);self.list.clear()
        if hasattr(self,'context_label'):self.context_label.setText(text('Dashed = geometry reference; blue = editable mesh topology. XY section, ','虚线 = 几何参考；蓝线 = 可编辑网格拓扑。XY 截面，')+f'{self.window.project.dimension}D · Z={self.window.project.depth:g} m')
        from .manual_reference import paint,points
        show_reference=not hasattr(self,'context_toggle') or self.context_toggle.isChecked()
        if show_reference:paint(scene,self.window.project,self.view.transform().m11())
        available={('node',int(n)) for n in g['nodes']}|{('edge',e['id']) for e in g['edges']}|{('face',f['key']) for f in fs}
        if self.selected not in available:self.selected=None;self.selection.setText(text('Select a node/curve/region to edit.','选择节点 / 曲线 / 区域进行编辑。'))
        def entry(label,tag):
            item=QListWidgetItem(label);item.setData(Qt.UserRole,tag);self.list.addItem(item)
            if tag==self.selected:self.list.setCurrentItem(item)
        for i,f in enumerate(fs):
            s=topo.settings(g,f); path=QPainterPath();path.addPolygon(QPolygonF([QPointF(x,-y) for x,y in f['poly']]));path.closeSubpath(); item=scene.addPath(path,QPen(Qt.NoPen),QBrush(QColor('#ead7cd' if s['role']=='hole' else '#a8d9df') if self.selected==('face',f['key']) else QColor(91,147,172,25)));item.setData(0,('face',f['key']));item.setZValue(-f['area']);entry(f'R{i+1} · {s["role"]} · {s["method"]}',('face',f['key'])); xy=[sum(v[k] for v in f['poly'])/len(f['poly']) for k in (0,1)]; label=scene.addSimpleText(f'R{i+1}'); label.setFlag(QGraphicsItem.ItemIgnoresTransformations); label.setPos(xy[0],-xy[1]); label.setData(0,('face',f['key'])); label.setZValue(3); label.setVisible(math.sqrt(f['area'])*self.view.transform().m11()>45 or self.selected==('face',f['key']))
        for e in g['edges']:
            pts=topo.samples(g,e);path=QPainterPath(QPointF(pts[0][0],-pts[0][1]))
            for x,y in pts[1:]:path.lineTo(x,-y)
            pen=QPen(QColor('#cf6422' if self.selected==('edge',e['id']) else '#174d70'),2);pen.setCosmetic(True);item=scene.addPath(path,pen);item.setData(0,('edge',e['id']));item.setZValue(2);mid=topo.point(g,e,.5);lab=scene.addSimpleText(f'E{e["id"]} [{e["count"]}]');lab.setFlag(QGraphicsItem.ItemIgnoresTransformations);lab.setPos(mid[0],-mid[1]);lab.setData(0,('edge',e['id']));lab.setZValue(4);lab.setVisible(sum(math.dist(a,b) for a,b in zip(pts,pts[1:]))*self.view.transform().m11()>75 or self.selected==('edge',e['id']));entry(f'E{e["id"]}: N{e["a"]} → N{e["b"]} · {e["kind"]} · n={e["count"]}',('edge',e['id']))
        for k,(x,y) in g['nodes'].items():
            item=scene.addEllipse(-4,-4,8,8,QPen(QColor('#145269')),QBrush(QColor('#e38b23' if self.selected==('node',int(k)) else '#fff')));item.setFlag(QGraphicsItem.ItemIgnoresTransformations);item.setPos(x,-y);item.setData(0,('node',int(k)));item.setZValue(8);entry(f'N{k}: ({x:g}, {y:g}) m',('node',int(k))); label=scene.addSimpleText(f'N{k}');label.setFlag(QGraphicsItem.ItemIgnoresTransformations);label.setPos(x,-y);label.setData(0,('node',int(k)));label.setZValue(9); label.setVisible(min([math.dist((x,y),q) for n,q in g['nodes'].items() if n!=k],default=1)*self.view.transform().m11()>28 or self.selected==('node',int(k)))
        if self.view.draft:
            pts=self.view.draft+([preview] if preview else []);path=QPainterPath(QPointF(pts[0][0],-pts[0][1]))
            for x,y in pts[1:]:path.lineTo(x,-y)
            pen=QPen(QColor('#e48627'),1,Qt.DashLine);pen.setCosmetic(True);scene.addPath(path,pen)
        bounds=list(g['nodes'].values())+(points(self.window.project) if show_reference else [])
        if show_reference and self.window.project.mesh_method=='Structured cylinder O-grid' and len(self.window.project.shapes)==1:
            s=self.window.project.shapes[0];r=self.window.project.outer_radius;bounds += [(s['x']-r,s['y']-r),(s['x']+r,s['y']+r)]
        if bounds:
            xs=[v[0] for v in bounds];ys=[v[1] for v in bounds];margin=max(max(xs)-min(xs),max(ys)-min(ys),.1)*.15;scene.setSceneRect(QRectF(min(xs)-margin,-max(ys)-margin,max(xs)-min(xs)+2*margin,max(ys)-min(ys)+2*margin))
        else:scene.setSceneRect(-10,-10,20,20)
        self.busy=False;self.apply.setEnabled(self.selected is not None);self.generate.setEnabled(bool(fs));self.activate_button.setEnabled(bool(fs))
    def select(self,tag):
        self.selected=tag;self.redraw();self.selection.setText(str(tag) if tag else text('Select a node/curve/region to edit.','选择节点 / 曲线 / 区域进行编辑。'))
        if not tag:return
        kind,key=tag
        if kind=='node':data=dict(zip(('x','y'),topo.node(self.graph,key)))
        elif kind=='edge':
            e=topo.edge(self.graph,key);data={**e,'mx':e.get('through',[0,0])[0],'my':e.get('through',[0,0])[1]}
            for k in ('mx','my'):self.inputs[kind,k].setEnabled(e['kind']=='arc')
        else:
            f=next(f for f in topo.faces(self.graph) if f['key']==key);ee=[topo.edge(self.graph,i) for i in f['edges']];rr=[e['ratio'] if i>0 else 1/e['ratio'] for e,i in zip(ee,f['edges'])];data={**topo.settings(self.graph,f),'nx':ee[0]['count'],'ny':ee[1]['count'],'gx':rr[0],'gy':rr[1]}
        if kind=='face':self.selection.setText(text('Region sides (CCW): ','区域边（逆时针）：')+' → '.join('E'+str(i) for i in f['edges']))
        self.form_stack.setCurrentIndex({'node':0,'edge':1,'face':2}[kind])
        for (category,k),widget in self.inputs.items():
            if category!=kind:continue
            value=data[k]
            if isinstance(widget,QComboBox):widget.setCurrentIndex(widget.findData(value))
            elif isinstance(widget,QLineEdit):widget.setText(str(value))
            else:widget.setValue(value)
    def apply_selected(self):
        if not self.selected:return
        kind,key=self.selected;data={k:w.currentData() if isinstance(w,QComboBox) else w.text() if isinstance(w,QLineEdit) else w.value() for (cat,k),w in self.inputs.items() if cat==kind}
        def apply(g):
            if kind=='node':g['nodes'][str(key)]=[data['x'],data['y']]
            elif kind=='edge':
                e=topo.edge(g,key);e.update({k:data[k] for k in ('count','ratio','patch')})
                if e['kind']=='arc':e['through']=[data['mx'],data['my']];topo.arc_geometry(g,e)
            else:topo.assign(g,key,data.pop('nx'),data.pop('ny'),data.pop('gx'),data.pop('gy'),**data)
        try:self.mutate(apply);self.select(self.selected);self.message(text('Selection applied. Shared mapped-edge counts and spacing ratios propagate; validate before generating.','所选对象已应用；共享映射边的单元数与间距比会传播，生成前请检查。'))
        except Exception as e:self.message(str(e),True)
    def check(self):
        try:
            fs,fluid=topo.validate(self.graph,self.backend.currentText());self.message(text(f'Topology valid: {len(fs)} regions / {len(fluid)} fluid. This is not a checkMesh result.',f'拓扑通过：{len(fs)} 个区域 / {len(fluid)} 个流体区域；这不等于 checkMesh 通过。'));return True
        except Exception as e:self.message(str(e),True);return False
    def activate(self):
        if not self.check():return False
        if 'system/blockMeshDict' in self.window.project.dictionary_overrides:self.message(text('A manual dictionary override exists. Review/remove it explicitly before using topology.','已有手动字典覆盖，请先明确核对/移除再使用拓扑。'),True);return False
        self.window.project.manual_mesh=copy.deepcopy(self.graph);self.window.project.reference_length=self.reference.value();self.window.project.mesh_method=topo.METHODS[0 if self.backend.currentText()=='blockMesh' else 1];self.window.refresh_tree();self.message(text('Manual topology is the actual mesh input. Automatic geometry is retained.','手动拓扑已成为实际网格输入；自动几何保留。'));return True
    def generate_mesh(self):
        if self.activate():self.window.mesh_only()
    def preset(self):
        if self.graph['edges'] and QMessageBox.question(self,text('Load preset','载入分块模板'),text('Replace topology? Undo restores this graph.','替换当前拓扑？可撤销恢复。'))!=QMessageBox.Yes:return
        try:
            from .manual_reference import cylinder_blocks
            graph=cylinder_blocks(self.window.project);self.mutate(lambda g:(g.clear(),g.update(graph)));self.reference.setValue(self.window.project.shapes[0]['width']);self.selected=None;self.redraw();self.fit()
        except Exception as e:self.message(str(e),True)
    def import_reference(self):
        try:
            from .manual_reference import import_boundaries
            self.mutate(lambda g:import_boundaries(g,self.window.project));self.backend.setCurrentText('Gmsh');self.fit();self.message(text('Actual boundary loops imported. Solids are holes. Assign/subdivide fluid regions; Gmsh selected for holes. Undo restores the graph. Reference shapes never silently alter the mesh.','已导入真实边界闭环，实体为排除区。请继续划分/指派流体区域；含孔区域默认用 Gmsh。可撤销；参考模型不会静默改变网格。'))
        except Exception as e:self.message(str(e),True)
    def exact(self):
        dialog=QDialog(self);dialog.setWindowTitle(text('Exact topology curve / SI metres','精确拓扑曲线 / SI 米'));box=QVBoxLayout(dialog);kind=QComboBox();kind.addItems(['line','arc']);box.addWidget(kind);form=QFormLayout();box.addLayout(form);coords={}
        for label in ('ax','ay','bx','by','mx','my'):
            w=ScientificSpin();w.setRange(-1e9,1e9);coords[label]=w;form.addRow(label+' / m',w)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);box.addWidget(buttons)
        if dialog.exec():
            try:
                v={k:w.value() for k,w in coords.items()};self.mutate(lambda g:topo.add_edge(g,topo.add_node(g,(v['ax'],v['ay'])),topo.add_node(g,(v['bx'],v['by'])),(v['mx'],v['my']) if kind.currentText()=='arc' else None))
            except Exception as e:self.message(str(e),True)
