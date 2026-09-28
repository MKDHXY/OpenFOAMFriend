"""Dimensioned CAD sketch with SI coordinates, snapping, regions, undo."""
import copy, math
from PySide6.QtCore import Qt,QPointF,QRectF,Signal,Slot
from PySide6.QtGui import QPainter,QPen,QBrush,QColor,QPainterPath,QPolygonF
from PySide6.QtWidgets import QGraphicsView,QGraphicsScene,QGraphicsPathItem,QGraphicsItem,QMenu,QStyle
from .i18n import text,tr

SCALE=50.0

class GeometryItem(QGraphicsPathItem):
    def paint(self,painter,option,widget=None):
        if self.isSelected():
            painter.save(); pen=QPen(QColor('#e98716'),2.5); pen.setCosmetic(True); painter.setPen(pen); painter.setBrush(QBrush(QColor(255,190,90,110))); painter.drawPath(self.path()); painter.restore()
        else: super().paint(painter,option,widget)

class Canvas(QGraphicsView):
    changed=Signal(); position=Signal(str); editRequested=Signal(str,int); toolChanged=Signal(str)
    selectionChanged=Signal(object)
    def __init__(self,project,parent=None):
        super().__init__(parent); self.project=project; self.tool='select'; self.snap=0.1; self.history=[]; self.future=[]; self.unit='m'
        self.setScene(QGraphicsScene(self)); self.setRenderHint(QPainter.Antialiasing)
        self.scene().selectionChanged.connect(self.emit_selection)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse); self.setMouseTracking(True)
        self.start=None; self.preview=None; self.poly_points=[]; self.ortho=False; self.object_snap=True; self.grid_snap=True; self.hover=None; self.snap_label=''; self.pan_last=None; self.move_before=None; self.rebuild(); self.fit()
    def fit(self): self.fitInView(self.scene().sceneRect(),Qt.KeepAspectRatio)
    @Slot()
    def emit_selection(self):
        from shiboken6 import isValid
        if isValid(self): self.selectionChanged.emit([i.data(0) for i in self.scene().selectedItems() if i.data(0)])
    def snapshot(self): return copy.deepcopy((self.project.shapes,self.project.regions,self.project.curves,self.project.mesh_method))
    def collection(self,kind): return {'shape':self.project.shapes,'region':self.project.regions,'curve':self.project.curves}[kind]
    def remember(self): self.history.append(self.snapshot()); self.future.clear()
    def undo(self):
        if self.poly_points:
            self.poly_points.pop(); self.start=self.poly_points[-1] if self.poly_points else None
            if self.preview: self.scene().removeItem(self.preview); self.preview=None
            self.viewport().update(); return
        if self.start is not None: self.cancel_draft(); return
        if self.history: self.future.append(self.snapshot()); self.project.shapes,self.project.regions,self.project.curves,self.project.mesh_method=self.history.pop(); self.rebuild(); self.changed.emit()
    def redo(self):
        if self.start is not None: self.cancel_draft(); return
        if self.future: self.history.append(self.snapshot()); self.project.shapes,self.project.regions,self.project.curves,self.project.mesh_method=self.future.pop(); self.rebuild(); self.changed.emit()
    def delete_selected(self):
        tags=[item.data(0) for item in self.scene().selectedItems() if item.data(0)]
        if not tags: return
        self.remember()
        for kind in ('shape','region','curve'):
            collection=self.collection(kind)
            for index in sorted({i for k,i in tags if k==kind},reverse=True): collection.pop(index)
        self.scene().clearSelection(); self.rebuild(); self.changed.emit()
    def duplicate_selected(self):
        tags=[item.data(0) for item in self.scene().selectedItems() if item.data(0)]
        if not tags: return
        self.remember(); duplicates=[]; delta=self.snap or min(self.project.xmax-self.project.xmin,self.project.ymax-self.project.ymin)/100
        for kind,index in tags:
            collection=self.collection(kind); s=copy.deepcopy(collection[index])
            if kind=='curve': s['points']=[[x+delta*5,y+delta*5] for x,y in s['points']]
            else: s['x']+=delta*5; s['y']+=delta*5
            if kind=='shape': s['name']=s.get('name','shape')+'_copy'
            collection.append(s)
            duplicates.append((kind,len(collection)-1))
        self.compatible_mesher(); self.scene().clearSelection(); self.rebuild(); self.select_tags(duplicates); self.changed.emit()
    def rebuild(self):
        selected=[i.data(0) for i in self.scene().selectedItems() if i.data(0)]
        self.preview=None; self.scene().clear(); p=self.project
        circle_domain=p.mesh_method=='Structured cylinder O-grid' and p.shapes
        if circle_domain:
            s=p.shapes[0]; domain=QRectF((s['x']-p.outer_radius)*SCALE,-(s['y']+p.outer_radius)*SCALE,2*p.outer_radius*SCALE,2*p.outer_radius*SCALE)
        else: domain=QRectF(p.xmin*SCALE,-p.ymax*SCALE,(p.xmax-p.xmin)*SCALE,(p.ymax-p.ymin)*SCALE)
        self.scene().setSceneRect(domain.adjusted(-80,-80,80,80))
        if circle_domain: self.scene().addEllipse(domain,QPen(QColor('#6184a8'),2),QBrush(QColor('#f8fbfe')))
        else: self.scene().addRect(domain,QPen(QColor('#6184a8'),2),QBrush(QColor('#f8fbfe')))
        for mode,collection in (('shape',p.shapes),('region',p.regions)):
            for i,s in enumerate(collection):
                x=s['x']*SCALE; y=-s['y']*SCALE; w=s['width']*SCALE; h=s['height']*SCALE
                rect=QRectF(x-w/2,y-h/2,w,h) if mode=='shape' else QRectF(x,y-h,w,h)
                path=QPainterPath()
                if mode=='region' or s['kind']=='rectangle': path.addRect(rect)
                elif s['kind']=='circle': path.addEllipse(rect)
                else:
                    from .geometry import vertices
                    path.addPolygon(QPolygonF([QPointF(x*SCALE,-y*SCALE) for x,y in vertices(s)])); path.closeSubpath()
                item=GeometryItem(path); item.setData(0,(mode,i)); item.setFlag(QGraphicsItem.ItemIsSelectable); item.setFlag(QGraphicsItem.ItemIsMovable)
                item.setPen(QPen(QColor('#009688' if mode=='region' else '#163e65'),1.5,Qt.DashLine if mode=='region' else Qt.SolidLine)); item.setBrush(QBrush(QColor(0,170,155,25) if mode=='region' else QColor('#b4c8dc'))); self.scene().addItem(item)
                label=self.scene().addText(f"R{i+1}: h={s['size']:g} {tr(s['direction'])}" if mode=='region' else f"{s.get('name',s['kind'])}  {s['width']:g} × {s['height']:g} m")
                label.setDefaultTextColor(QColor('#244666')); label.setPos(rect.left(),rect.bottom()+4); label.setFlag(QGraphicsItem.ItemIgnoresTransformations)
                label.setData(1,item); label.setAcceptedMouseButtons(Qt.NoButton); item.setSelected((mode,i) in selected)
        for i,c in enumerate(p.curves):
            path=QPainterPath(QPointF(c['points'][0][0]*SCALE,-c['points'][0][1]*SCALE))
            for x,y in c['points'][1:]: path.lineTo(x*SCALE,-y*SCALE)
            item=GeometryItem(path); item.setPen(QPen(QColor('#cb7b18'),2,Qt.DashLine)); item.setData(0,('curve',i)); item.setFlags(QGraphicsItem.ItemIsSelectable|QGraphicsItem.ItemIsMovable); self.scene().addItem(item)
            length=sum(math.dist(a,b) for a,b in zip(c['points'],c['points'][1:])); label=self.scene().addText(f"{c.get('name','construction')} · L={length:g} m"); label.setPos(path.boundingRect().left(),path.boundingRect().bottom()); label.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            label.setData(1,item); label.setAcceptedMouseButtons(Qt.NoButton); item.setSelected(('curve',i) in selected)
    def select_tags(self,tags):
        self.scene().blockSignals(True)
        for item in self.scene().items():
            if item.data(0): item.setSelected(item.data(0) in tags)
        self.scene().blockSignals(False); self.selectionChanged.emit(tags); self.viewport().update()
    def object_at(self,pos):
        item=self.itemAt(pos)
        if item and item.data(1): return item.data(1)
        if item and item.data(0): return item
        return None
    def add_curve(self,points,name=None):
        clean=[]
        for p in points:
            if not clean or math.dist(clean[-1],p)>1e-12: clean.append(list(p))
        if len(clean)<2: return
        self.remember(); self.project.curves.append({'name':name or 'Construction '+str(len(self.project.curves)+1),'points':clean}); self.rebuild(); self.changed.emit()
    def finish_polyline(self):
        points=self.poly_points[:]; self.cancel_draft()
        if self.tool=='polygon':
            try:
                from .geometry import polygon
                solid=polygon(points,'polygon'+str(len(self.project.shapes)+1))
                self.remember(); self.project.shapes.append(solid); self.compatible_mesher(); self.rebuild(); self.changed.emit()
            except ValueError as e: self.position.emit(str(e))
        else: self.add_curve(points)
    def compatible_mesher(self):
        p=self.project
        ogrid_ok=len(p.shapes)==1 and p.shapes[0]['kind']=='circle' and abs(p.shapes[0]['width']-p.shapes[0]['height'])<1e-9
        if (p.mesh_method=='Structured cylinder O-grid' and not ogrid_ok) or (p.mesh_method=='Structured partitioned box' and p.shapes):
            if 'system/blockMeshDict' not in p.dictionary_overrides:
                p.mesh_method='Gmsh triangle / prism'; self.position.emit(text('Geometry now uses Gmsh; choose mesh controls in Meshing.','几何已改用 Gmsh；请在网格设置中选择控制参数。'))
    def set_tool(self,tool):
        self.poly_points=[]; self.start=None; self.hover=None
        if self.preview: self.scene().removeItem(self.preview); self.preview=None
        self.tool=tool; self.setDragMode(QGraphicsView.ScrollHandDrag if tool=='pan' else QGraphicsView.RubberBandDrag if tool=='select' else QGraphicsView.NoDrag)
        self.setCursor(Qt.ArrowCursor if tool in ('select','pan') else Qt.CrossCursor)
        self.toolChanged.emit(tool); self.viewport().update()
    def anchors(self):
        points=[(0.,0.,text('Origin','原点'))]
        for c in self.project.curves:
            points.extend((x,y,text('Endpoint','端点')) for x,y in c['points'])
            points.extend(((a[0]+b[0])/2,(a[1]+b[1])/2,text('Midpoint','中点')) for a,b in zip(c['points'],c['points'][1:]))
        for s in self.project.shapes:
            x,y=s['x'],s['y']; w,h=s['width']/2,s['height']/2; points.append((x,y,text('Centre','中心')))
            corners=[(x-w,y),(x+w,y),(x,y-h),(x,y+h)] if s['kind']=='circle' else [(x-w,y-h),(x+w,y-h),(x,y+h)] if s['kind']=='triangle' else [(x+u*w,y+v*h) for u in (-1,1) for v in (-1,1)]
            if s['kind']=='polygon':
                from .geometry import vertices
                corners=vertices(s)
            points.extend((a,b,text('Quadrant / corner','象限点 / 角点')) for a,b in corners)
        points.extend((x,y,text('Vertex','顶点')) for x,y in self.poly_points)
        return points
    def point(self,pos,modifiers=Qt.NoModifier):
        v=self.mapToScene(pos); x=v.x()/SCALE; y=-v.y()/SCALE
        self.snap_label=''; raw=(x,y)
        if not modifiers & Qt.AltModifier:
            if self.grid_snap and self.snap: x,y=round(x/self.snap)*self.snap,round(y/self.snap)*self.snap; self.snap_label=text('Grid','网格吸附')
            if self.object_snap:
                nearest=min(self.anchors(),key=lambda p:math.dist(raw,p[:2]))
                if math.dist(raw,nearest[:2])*SCALE*self.transform().m11()<=9: x,y=nearest[:2]; self.snap_label=nearest[2]
        if self.start and self.tool in ('line','polyline','measure') and (self.ortho or modifiers & Qt.ShiftModifier):
            a,b=self.start
            if abs(x-a)>=abs(y-b): y=b
            else: x=a
            self.snap_label=text('Orthogonal','正交约束')
        self.hover=(x,y); return x,y
    def cancel_draft(self):
        active=bool(self.start is not None or self.poly_points); self.start=None; self.poly_points=[]
        if self.preview: self.scene().removeItem(self.preview); self.preview=None
        self.viewport().update(); return active
    def mousePressEvent(self,e):
        if e.button()==Qt.MiddleButton: self.pan_last=e.position().toPoint(); self.setCursor(Qt.ClosedHandCursor); e.accept(); return
        if e.button()==Qt.RightButton and self.tool in ('polyline','polygon') and self.poly_points: self.finish_polyline(); self.suppress_context=True; e.accept(); return
        if e.position().x()<54 or e.position().y()<24: e.accept(); return
        if e.button()!=Qt.LeftButton: return super().mousePressEvent(e)
        if self.tool=='select':
            target=self.object_at(e.position().toPoint()); actual=self.itemAt(e.position().toPoint())
            if target is not None and actual is not target:
                if not e.modifiers() & Qt.ControlModifier: self.scene().clearSelection()
                target.setSelected(not target.isSelected() if e.modifiers() & Qt.ControlModifier else True); e.accept(); return
        if self.tool=='erase':
            item=self.itemAt(e.position().toPoint())
            if item and item.data(0):
                self.remember(); kind,index=item.data(0); self.collection(kind).pop(index); self.rebuild(); self.changed.emit()
            return
        if self.tool in ('polyline','polygon'):
            p=self.point(e.position().toPoint(),e.modifiers())
            if not self.poly_points or math.dist(p,self.poly_points[-1])>1e-12: self.poly_points.append(p)
            self.start=self.poly_points[-1]; return
        if self.tool in ('line','circle','rectangle','triangle','region','measure'):
            self.line_press=e.position().toPoint(); self.line_second=self.start is not None
            if self.start is None: self.start=self.point(e.position().toPoint(),e.modifiers())
            return
        if self.tool in ('circle','rectangle','triangle','region','measure','line'):
            self.start=self.point(e.position().toPoint(),e.modifiers()); return
        if self.tool=='select': self.move_before=self.snapshot()
        super().mousePressEvent(e)
    def mouseMoveEvent(self,e):
        if self.pan_last is not None:
            now=e.position().toPoint(); delta=now-self.pan_last; self.pan_last=now; self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x()); self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y()); return
        x,y=self.point(e.position().toPoint(),e.modifiers()); self.position.emit(f'x {x:.5g} m   y {y:.5g} m · {self.snap_label}'); self.viewport().update()
        if self.start:
            a,b=self.start; rect=QRectF(min(a,x)*SCALE,-max(b,y)*SCALE,abs(x-a)*SCALE,abs(y-b)*SCALE)
            path=QPainterPath()
            if self.tool=='circle':
                radius=math.hypot(x-a,y-b)*SCALE; path.addEllipse(QPointF(a*SCALE,-b*SCALE),radius,radius)
            elif self.tool=='triangle': path.addPolygon(QPolygonF([rect.bottomLeft(),rect.bottomRight(),QPointF(rect.center().x(),rect.top())])); path.closeSubpath()
            elif self.tool in ('measure','line','polyline','polygon'):
                path=QPainterPath(); points=self.poly_points+[(x,y)] if self.tool in ('polyline','polygon') else [(a,b),(x,y)]
                path.moveTo(points[0][0]*SCALE,-points[0][1]*SCALE)
                for u,v in points[1:]: path.lineTo(u*SCALE,-v*SCALE)
            else: path.addRect(rect)
            if self.preview: self.preview.setPath(path)
            else:
                pen=QPen(QColor('#0076c9'),2); pen.setCosmetic(True); self.preview=self.scene().addPath(path,pen); self.preview.setAcceptedMouseButtons(Qt.NoButton)
            return
        super().mouseMoveEvent(e)
    def mouseReleaseEvent(self,e):
        if e.button()==Qt.MiddleButton: self.pan_last=None; self.setCursor(Qt.ArrowCursor if self.tool in ('select','pan') else Qt.CrossCursor); return
        if e.button()!=Qt.LeftButton: return super().mouseReleaseEvent(e)
        if self.tool in ('polyline','polygon'): return
        if self.tool in ('line','circle','rectangle','triangle','region','measure') and self.start is not None:
            # A stationary first click keeps the draft. A second click commits.
            # Press-drag-release remains available for existing users.
            dragged=(e.position().toPoint()-getattr(self,'line_press',e.position().toPoint())).manhattanLength()>5
            if not getattr(self,'line_second',False) and not dragged:
                self.position.emit('Choose endpoint / 点击第二个端点 · Esc: cancel'); return
            if self.tool=='line':
                end=self.point(e.position().toPoint(),e.modifiers()); start=self.start; self.cancel_draft()
                if math.dist(start,end)>1e-12: self.add_curve([start,end])
                return
        if self.start:
            a,b=self.start; x,y=self.point(e.position().toPoint(),e.modifiers()); self.start=None
            if self.preview: self.scene().removeItem(self.preview); self.preview=None
            w=abs(x-a); h=abs(y-b)
            if self.tool=='circle': w=h=2*math.hypot(x-a,y-b)
            if self.tool=='line': self.add_curve([(a,b),(x,y)]); return
            if self.tool=='measure':
                self.position.emit(f'Distance = {math.hypot(x-a,y-b):.8g} m'); return
            if min(w,h)>1e-12:
                self.remember()
                if self.tool=='region': self.project.regions.append({'x':min(a,x),'y':min(b,y),'width':w,'height':h,'size':self.project.cell_size/2,'direction':'uniform','ratio':1.0})
                else:
                    self.project.shapes.append({'kind':self.tool,'x':a if self.tool=='circle' else (a+x)/2,'y':b if self.tool=='circle' else (b+y)/2,'width':w,'height':h,'name':f'{self.tool}{len(self.project.shapes)+1}'})
                self.compatible_mesher(); self.rebuild(); self.changed.emit()
            return
        super().mouseReleaseEvent(e)
        if self.tool=='select':
            moved=False
            for item in self.scene().selectedItems():
                if item.data(0) and not item.pos().isNull():
                    kind,index=item.data(0); s=self.collection(kind)[index]; dx=item.pos().x()/SCALE; dy=-item.pos().y()/SCALE
                    if kind=='curve': s['points']=[[x+dx,y+dy] for x,y in s['points']]
                    else: s['x']+=dx; s['y']+=dy
                    moved=True
            if moved:
                if self.move_before is not None: self.history.append(self.move_before); self.future.clear()
                self.rebuild(); self.changed.emit()
            self.move_before=None
    def mouseDoubleClickEvent(self,e):
        if self.tool in ('polyline','polygon'): self.finish_polyline(); return
        item=self.object_at(e.position().toPoint())
        if item and item.data(0): self.editRequested.emit(*item.data(0)); return
        super().mouseDoubleClickEvent(e)
    def contextMenuEvent(self,e):
        if getattr(self,'suppress_context',False): self.suppress_context=False; return
        if self.start is not None or self.poly_points: return
        item=self.object_at(e.pos()); menu=QMenu(self)
        if item and item.data(0):
            self.scene().clearSelection(); item.setSelected(True); kind,index=item.data(0)
            menu.addAction(text('Edit exact dimensions','编辑精确尺寸'),lambda:self.editRequested.emit(kind,index)); menu.addAction(text('Duplicate','复制对象'),self.duplicate_selected); menu.addAction(text('Delete','删除对象'),self.delete_selected)
        menu.addAction(tr('Undo'),self.undo); menu.addAction(tr('Redo'),self.redo); menu.addAction(tr('Fit'),self.fit); menu.exec(e.globalPos())
    def keyPressEvent(self,e):
        if self.tool in ('polyline','polygon') and self.poly_points and (e.key()==Qt.Key_Backspace or (e.key()==Qt.Key_Z and e.modifiers() & Qt.ControlModifier)):
            self.poly_points.pop(); self.start=self.poly_points[-1] if self.poly_points else None
            if self.preview: self.scene().removeItem(self.preview); self.preview=None
            self.viewport().update(); return
        toggles={Qt.Key_F3:'object_snap',Qt.Key_F8:'ortho',Qt.Key_F9:'grid_snap'}
        if e.key() in toggles: key=toggles[e.key()]; setattr(self,key,not getattr(self,key)); self.toolChanged.emit(self.tool); return
        if e.key()==Qt.Key_Delete: self.delete_selected(); return
        if e.modifiers() & Qt.ControlModifier:
            if e.key()==Qt.Key_Z: self.undo(); return
            if e.key()==Qt.Key_Y: self.redo(); return
            if e.key()==Qt.Key_D: self.duplicate_selected(); return
        if e.key() in (Qt.Key_Return,Qt.Key_Enter) and self.tool in ('polyline','polygon'): self.finish_polyline(); return
        if e.key()==Qt.Key_Escape:
            if not self.cancel_draft(): self.set_tool('select')
            return
        shortcuts={Qt.Key_V:'select',Qt.Key_H:'pan',Qt.Key_L:'line',Qt.Key_P:'polyline',Qt.Key_B:'polygon',Qt.Key_C:'circle',Qt.Key_R:'rectangle',Qt.Key_G:'region',Qt.Key_M:'measure'}
        if e.key() in shortcuts and not e.modifiers(): self.set_tool(shortcuts[e.key()]); return
        super().keyPressEvent(e)
    def wheelEvent(self,e):
        factor=1.2 if e.angleDelta().y()>0 else 1/1.2
        current=self.transform().m11()
        if .01<current*factor<100: self.scale(factor,factor)
    def drawBackground(self,painter,rect):
        painter.fillRect(rect,QColor('#edf3f8')); scale=self.transform().m11()
        step=10**math.ceil(math.log10(60/max(scale*SCALE,1e-6)))
        pen=QPen(QColor('#d5e1eb')); pen.setCosmetic(True); painter.setPen(pen)
        left=math.floor(rect.left()/SCALE/step)*step; top=math.floor(rect.top()/SCALE/step)*step
        for x in range(300):
            value=(left+x*step)*SCALE
            if value>rect.right(): break
            painter.drawLine(QPointF(value,rect.top()),QPointF(value,rect.bottom()))
        for y in range(300):
            value=(top+y*step)*SCALE
            if value>rect.bottom(): break
            painter.drawLine(QPointF(rect.left(),value),QPointF(rect.right(),value))
    def paintEvent(self,e):
        super().paintEvent(e); painter=QPainter(self.viewport()); painter.fillRect(0,0,self.width(),24,QColor('#e2ebf3')); painter.fillRect(0,0,54,self.height(),QColor('#e2ebf3')); painter.setPen(QColor('#35536b'))
        scale=self.transform().m11(); step=10**math.ceil(math.log10(65/max(scale*SCALE,1e-9))); factor={'m':1,'cm':100,'mm':1000}[self.unit]
        left=self.mapToScene(55,24).x()/SCALE; right=self.mapToScene(self.viewport().width(),24).x()/SCALE
        v=math.ceil(left/step)*step
        while v<=right:
            x=self.mapFromScene(v*SCALE,0).x(); painter.drawLine(x,18,x,24); painter.drawText(x-24,15,f'{v*factor:.4g}'); v+=step
        bottom=-self.mapToScene(54,self.viewport().height()).y()/SCALE; top=-self.mapToScene(54,24).y()/SCALE; v=math.ceil(bottom/step)*step
        while v<=top:
            y=self.mapFromScene(0,-v*SCALE).y(); painter.drawLine(47,y,54,y); painter.drawText(4,y-3,f'{v*factor:.4g}'); v+=step
        painter.drawText(5,16,self.unit); painter.end()
        if self.hover and self.tool not in ('select','pan'):
            painter=QPainter(self.viewport()); q=self.mapFromScene(self.hover[0]*SCALE,-self.hover[1]*SCALE); pen=QPen(QColor('#db8316') if self.snap_label else QColor('#0076c9'),1); painter.setPen(pen); painter.drawLine(q.x()-12,q.y(),q.x()+12,q.y()); painter.drawLine(q.x(),q.y()-12,q.x(),q.y()+12); painter.drawRect(q.x()-4,q.y()-4,8,8)
            value=self.snap_label
            if self.start:
                a,b=self.start; dx=self.hover[0]-a; dy=self.hover[1]-b
                value+=f' · L={math.hypot(dx,dy):.5g} m · {math.degrees(math.atan2(dy,dx)):.1f}°' if self.tool in ('line','polyline','measure') else f' · D={2*math.hypot(dx,dy):.5g} m' if self.tool=='circle' else f' · {abs(dx):.5g} × {abs(dy):.5g} m'
            box=painter.boundingRect(QRectF(q.x()+16,q.y()+16,600,32),Qt.AlignLeft,value); box=box.adjusted(-5,-3,5,3); painter.fillRect(box,QColor('#fff9e8')); painter.drawText(box.adjusted(5,3,-5,-3),Qt.AlignLeft,value); painter.end()
