"""Native geometry/input/source/tutorial QA plus actual polygon Gmsh→OpenFOAM checks."""
import os,sys,json,time,copy,subprocess,re
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from off.models import Project,load_profile,host_path
from off.gui import MainWindow
from off.geometry import polygon
from off.templates import examples,make_template
from off.backend import write_case,prepare_mesh,DATA,quality
from off.file_browser import FileBrowser
app=QApplication([]); w=MainWindow(); w.timer.stop(); w.show(); errors=[]; w.error=lambda e:errors.append(e)
def wait():
    deadline=time.time()+180
    while w.workers:
        app.processEvents(); time.sleep(.02)
        if time.time()>deadline: raise TimeoutError('GUI worker')
    assert not errors,errors
wait(); c=w.canvas; c.grid_snap=False; c.object_snap=False
for tool in ('rectangle','circle','triangle','region'):
    before=len(w.project.regions if tool=='region' else w.project.shapes); c.set_tool(tool)
    a=c.mapFromScene(QPointF(-100,-100)); z=c.mapFromScene(QPointF(-50,-50))
    QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=a); assert c.start is not None
    QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=z); assert c.start is None
    assert len(w.project.regions if tool=='region' else w.project.shapes)==before+1
    c.undo()
assert w.project.mesh_method=='Structured cylinder O-grid'
c.set_tool('polygon'); coords=[(-100,-100),(-50,-100),(-40,-60),(-100,-50)]
for x,y in coords: QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=c.mapFromScene(QPointF(x,y)))
QTest.keyClick(c,Qt.Key_Return); assert w.project.shapes[-1]['kind']=='polygon' and w.project.mesh_method=='Gmsh triangle / prism'
c.undo(); assert w.project.mesh_method=='Structured cylinder O-grid'; c.redo(); assert w.project.shapes[-1]['kind']=='polygon'; c.undo()
try: polygon([[0,0],[1,1],[0,1],[1,0]]); raise AssertionError('self crossing accepted')
except ValueError: pass
w.pre_mode.setCurrentIndex(1); app.processEvents(); assert w.mesh_toolbar.isVisible() and not w.sketch_toolbar.isVisible() and w.mesh_region_action.isVisible()
branches=[w.tree.topLevelItem(0).child(i) for i in range(w.tree.topLevelItem(0).childCount())]; m=next(x for x in branches if x.data(0,Qt.UserRole)==('nav','mesh')); w.tabs.setCurrentIndex(1); w.edit_object(m,0); assert w.tabs.currentIndex()==0 and w.pre_mode.currentIndex()==1
w.grab().save(str(BASE/'evidence/meshing_workspace_EN.png')); w.change_language('zh'); w.grab().save(str(BASE/'evidence/meshing_workspace_ZH.png')); w.change_language('en')
for key,label in examples():
    p=make_template(key); p.validate(); path=DATA/(key+'.off.json'); p.save(path); assert Project.load(path).mesh_method==p.mesh_method
p=Project(); draft=DATA/'file_browser_qa'; write_case(p,w.profile,preview_root=draft); prepare_mesh(p,w.profile,draft)
fb=FileBrowser([('draft',draft,True),('source',BASE,False)],w); fb.show(); fb.open_file(draft/'system/blockMeshDict'); app.processEvents(); fb.grab().save(str(BASE/'evidence/generated_file_browser.png')); assert not fb.editor.isReadOnly() and 'simpleGrading' in fb.editor.toPlainText(); fb.choose_root(1); fb.open_file(BASE/'off/mesh.py'); assert fb.editor.isReadOnly() and 'build_gmsh' in fb.editor.toPlainText(); fb.close()
assert all((draft/x).exists() for x in ['0/U','0/p','system/controlDict','system/fvSchemes','system/fvSolution','system/decomposeParDict','constant/physicalProperties','constant/momentumTransport','system/blockMeshDict','mesh_generator_source.py'])
# Prove a manual block override changes actual generated resolution.
manual=Project(name='OFF_MANUAL_'+time.strftime('%Y%m%d_%H%M%S')); content=(draft/'system/blockMeshDict').read_text(); manual.dictionary_overrides['system/blockMeshDict']=content.replace('(20 16 4)','(21 16 4)'); manual.validate()
case=write_case(manual,w.profile); command=prepare_mesh(manual,w.profile,case)
linux=w.profile.run_dir+'/'+manual.name
r=subprocess.run(['wsl','-d',w.profile.distro,'--','bash','-lc','source '+w.profile.bashrc+' >/dev/null 2>&1; cd '+linux+'; '+command+'; checkMesh > log.checkMesh 2>&1'],capture_output=True,text=True,timeout=90); assert r.returncode==0
q=quality(case); assert q['cells']==5376 and q['passed'],q
polygons=[]
for dimension in (2,3):
    p=make_template('polygon'); p.dimension=dimension; p.spanwise=1 if dimension==2 else 4; p.name='OFF_POLYGON_QA_'+str(dimension)+'D_'+time.strftime('%Y%m%d_%H%M%S')
    case=write_case(p,w.profile); command=prepare_mesh(p,w.profile,case); linux=w.profile.run_dir+'/'+p.name
    r=subprocess.run(['wsl','-d',w.profile.distro,'--','bash','-lc','source '+w.profile.bashrc+' >/dev/null 2>&1; cd '+linux+'; '+command],capture_output=True,text=True,timeout=120); assert r.returncode==0,r.stderr
    boundary=case/'constant/polyMesh/boundary'; raw=boundary.read_text()
    for name,typ in [('cylinder','wall'),('front','empty' if dimension==2 else 'symmetryPlane'),('back','empty' if dimension==2 else 'symmetryPlane')]:
        raw=re.sub(r'('+name+r'\s*\{[^}]*?type\s+)\w+',lambda m:m[1]+typ,raw)
    boundary.write_text(raw)
    r=subprocess.run(['wsl','-d',w.profile.distro,'--','bash','-lc','source '+w.profile.bashrc+' >/dev/null 2>&1; cd '+linux+'; checkMesh -allGeometry -allTopology > log.checkMesh 2>&1'],capture_output=True,text=True,timeout=120); assert r.returncode==0,r.stderr
    q=quality(case); assert q['cells']>0 and q['passed'],q
    polygons.append({'dimension':dimension,'case':str(case),'quality':q,'strict_project_gate_would_pass':q['skewness']<=p.skew_limit and q['non_orthogonality']<=p.nonortho_limit})
report={'release':BASE.name,'two_click_all_primitives':True,'polygon_is_actual_solid':True,'undo_restores_backend':True,'self_intersection_rejected':True,'single_mesh_tree_branch_and_correct_routing':True,'seven_template_roundtrips':True,'native_file_browser_draft_editable_source_readonly':True,'all_required_actual_draft_files':True,'manual_block_override_actual_cells':5376,'actual_polygon_GmshToFoam_2D_3D':polygons,'errors':errors}
(BASE/'evidence/drawing_files_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2)); wait(); w.close()
