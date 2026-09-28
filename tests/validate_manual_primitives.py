"""Extra manual primitives and real conformal partition / hole / 2D compilation."""
import os,sys,time,json
from pathlib import Path
os.environ['OFF_LANGUAGE']='zh';BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication,QToolButton
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project,load_profile
from off import manual_topology as t
from off.backend import write_case,prepare_mesh,wsl,quality
app=QApplication([]);w=MainWindow();w.show();w.timer.stop();errors=[];w.error=errors.append
out=BASE/'evidence/manual_topology';rows=[]
def pump(ms=80):
 end=time.time()+ms/1000
 while time.time()<end:app.processEvents();time.sleep(.01)
while w.workers:pump()
w.open_manual_topology();ed=w.manual_editor;c=ed.view
for tool,points in [('rectangle',[(-4,-2),(4,2)]),('circle',[(0,0),(.5,0)])]:
 a=ed.actions[tool][0];b=next(b for b in ed.findChildren(QToolButton) if b.defaultAction() is a);QTest.mouseClick(b,Qt.LeftButton);pump()
 for x,y in points:QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=c.mapFromScene(x,-y));pump()
assert len(ed.graph['edges'])==8 and len(t.faces(ed.graph))==2
for f in t.faces(ed.graph):
 hole=f['area']<2;ed.graph['regions'][f['key']]={**t.defaults(),'method':'tri','role':'hole' if hole else 'fluid','size':.5}
 if hole:
  for eid in f['edges']:t.edge(ed.graph,eid)['patch']='cylinder'
g=ed.graph
# Generate real hole topology in 3D; default quality limits remain explicit.
p=Project(name='OFF_MANUAL_HOLE_'+time.strftime('%Y%m%d_%H%M%S'),mesh_method=t.METHODS[1],manual_mesh=g,reference_length=1)
profile=load_profile()
def generate(p):
 case=write_case(p,profile);cmd=prepare_mesh(p,profile,case);r=wsl(profile,'source '+profile.bashrc+' >/dev/null 2>&1; cd '+profile.run_dir+'/'+p.name+'; '+cmd,120);assert r.returncode==0
 if p.dimension==2:
  import re
  boundary=case/'constant/polyMesh/boundary';raw=boundary.read_text()
  for name in ['front','back']:raw=re.sub(r'('+name+r'\s*\{[^}]*?type\s+)\w+',lambda m:m[1]+'empty',raw)
  boundary.write_text(raw)
 r=wsl(profile,'source '+profile.bashrc+' >/dev/null 2>&1; cd '+profile.run_dir+'/'+p.name+'; checkMesh -allGeometry -allTopology > log.checkMesh 2>&1',90);q=quality(case);assert r.returncode==0 and q['passed'],q
 row=dict(name=p.name,dimension=p.dimension,cells=q['cells'],quality=q,case=str(case),passes_project_limits=q['skewness']<=p.skew_limit and q['non_orthogonality']<=p.nonortho_limit);rows.append(row);return case
case=generate(p);p.save(out/'circle_hole_project.off.json')
# Triangle via continuous actual polyline clicks.
w.project=Project();w.canvas.project=w.project;w.refresh_tree();ed.reload();ed.fit();a=ed.actions['polyline'][0];QTest.mouseClick(next(b for b in ed.findChildren(QToolButton) if b.defaultAction() is a),Qt.LeftButton);pump()
for x,y in [(0,0),(2,0),(1,2),(0,0)]:QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=c.mapFromScene(x,-y));pump()
QTest.keyClick(c,Qt.Key_Escape);assert len(ed.graph['edges'])==3 and len(t.faces(ed.graph))==1
f=t.faces(ed.graph)[0];ed.graph['regions'][f['key']]={**t.defaults(),'method':'tri'}
p=Project(name='OFF_MANUAL_TRIANGLE_2D_'+time.strftime('%Y%m%d_%H%M%S'),dimension=2,spanwise=1,mesh_method=t.METHODS[1],manual_mesh=ed.graph,reference_length=2);case=generate(p)
# Mimic queue's explicit front/back patch type conversion before independent 2D check.
b=case/'constant/polyMesh/boundary';s=b.read_text();import re
for name in ['front','back']:s=re.sub(r'('+name+r'\s*\{[^}]*?type\s+)\w+',lambda m:m[1]+'empty',s)
b.write_text(s);r=wsl(profile,'source '+profile.bashrc+' >/dev/null 2>&1; cd '+profile.run_dir+'/'+p.name+'; checkMesh -allGeometry -allTopology > log.checkMesh 2>&1',90);assert r.returncode==0 and quality(case)['passed'];ed.grab().save(str(out/'manual_polyline_triangle_ZH.png'))
# Distinct region counts with one shared interface and real monotone grading.
g=t.empty();ns=[t.add_node(g,xy) for xy in [(-4,-2),(4,-2),(4,2),(-4,2)]]
for i in range(4):t.add_edge(g,ns[i],ns[(i+1)%4])
bottom,_=t.split(g,1,(0,-2));top,_=t.split(g,3,(0,2));t.add_edge(g,bottom,top)
fs=t.faces(g);left=min(fs,key=lambda f:sum(x for x,y in f['poly'])/len(f['poly']));right=next(f for f in fs if f is not left)
def assign_xy(f,horizontal):
 a,b=[t.node(g,n) for n in f['vertices'][:2]]
 if abs(b[0]-a[0])>abs(b[1]-a[1]):t.assign(g,f['key'],horizontal,8,2 if horizontal==12 else 1,1)
 else:t.assign(g,f['key'],8,horizontal,1,2 if horizontal==12 else 1)
assign_xy(left,12);assign_xy(right,6)
for dim,expected in [(2,144),(3,576)]:
 p=Project(name='OFF_MANUAL_REGIONS_'+str(dim)+'D_'+time.strftime('%Y%m%d_%H%M%S'),dimension=dim,spanwise=1 if dim==2 else 4,reference_length=1,mesh_method=t.METHODS[0],manual_mesh=g);case=generate(p);assert quality(case)['cells']==expected;assert any(x in (case/'system/blockMeshDict').read_text() for x in ['simpleGrading (2 1 1)','simpleGrading (1 2 1)'])
# Actual mouse selection/capture for per-region setup; fresh project replaces only this QA window.
w.project=p;w.canvas.project=p;w.refresh_tree();w.open_manual_topology();ed.select(('face',left['key']));ed.actions['select'][0].trigger();ed.grab().save(str(out/'manual_regions_graded_ZH.png'));w.change_language('en');ed.grab().save(str(out/'manual_regions_graded_EN.png'))
# Edits change signatures; older schema=1 files still load.
from off.workbench import signature,MESH_KEYS
old=signature(p,MESH_KEYS);p.manual_mesh['edges'][0]['count']+=1;assert old!=signature(p,MESH_KEYS)
legacy=Project();d=__import__('dataclasses').asdict(legacy);d.pop('manual_mesh');d['schema']=1;file=out/'legacy_schema1.off.json';file.write_text(json.dumps(d));assert Project.load(file).manual_mesh=={}
report=dict(release=BASE.name,real_mouse_rectangle_circle_polyline=True,real_Gmsh_hole_and_2D_triangle=True,region_12x8_and_6x8_real_cells=True,real_monotone_grading_ratio=2,manual_edits_invalidate_mesh_evidence=True,legacy_schema1_readable=True,meshes=rows,errors=errors);(out/'extended_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));assert not errors;w.close()
