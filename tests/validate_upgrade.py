"""Bilingual UI, drawing tools, token-safe dictionaries and guided real meshes."""
import sys,os,time,json,copy
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt,QTimer,QPoint
from PySide6.QtWidgets import QApplication,QPushButton,QDialog
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from off.gui import MainWindow,Properties
from off.models import Project,Profile
from off.backend import BASE,wsl
from off.dictionary_editor import DictionaryDialog,tokens,format_foam
from off.mesh_assistant import MeshAssistant,recommended
from off.i18n import tr

app=QApplication(sys.argv); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=lambda x:errors.append(x); out=BASE/'evidence'; out.mkdir(exist_ok=True)
while w.workers: QTest.qWait(50)
w.change_language('zh'); assert any(b.text()=='自动网格助手' for b in w.findChildren(QPushButton)); assert w.tabs.tabText(0)=='01  几何'; assert w.viewer.slice.currentData()=='Full volume'
props=Properties('Meshing',{'mesh_method':'Gmsh triangle / prism','cell_size':1.},w,{'mesh_method':['Structured cylinder O-grid','Gmsh triangle / prism']}); assert props.inputs['mesh_method'].currentText()=='自动三角形 / 棱柱'; assert props.values()['mesh_method']=='Gmsh triangle / prism'; props.close()
w.change_language('en'); assert w.tabs.tabText(0)=='01  GEOMETRY'
# Actual sketch input, undo/redo, multi-object duplication and deletion.
canvas=w.canvas; original=copy.deepcopy(w.project); canvas.set_tool('triangle'); a=canvas.mapFromScene(-150,150); b=canvas.mapFromScene(-75,75)
QTest.mousePress(canvas.viewport(),Qt.LeftButton,pos=a); QTest.mouseMove(canvas.viewport(),b); QTest.mouseRelease(canvas.viewport(),Qt.LeftButton,pos=b); assert len(w.project.shapes)==2
canvas.undo(); assert len(w.project.shapes)==1; canvas.redo(); assert len(w.project.shapes)==2
item=next(x for x in canvas.scene().items() if x.data(0)==('shape',1)); item.setSelected(True); canvas.duplicate_selected(); assert len(w.project.shapes)==3
item=next(x for x in canvas.scene().items() if x.data(0)==('shape',2)); item.setSelected(True); canvas.delete_selected(); assert len(w.project.shapes)==2
w.project=original; canvas.project=w.project; canvas.rebuild(); w.refresh_tree()
tag=time.strftime('%Y%m%d_%H%M%S'); w.project.name='OFF_ASSISTANT_'+tag
captured={}
def accept_assistant():
    dlg=next(x for x in app.topLevelWidgets() if isinstance(x,MeshAssistant) and x.isVisible())
    assert dlg.method.currentData()=='Structured cylinder O-grid'; assert dlg.project().radial*dlg.project().circumferential*dlg.project().spanwise==5120
    dlg.grab().save(str(out/'mesh_assistant_EN.png')); btn=next(b for b in dlg.findChildren(QPushButton) if b.text()=='Generate and check real preview'); QTest.mouseClick(btn,Qt.LeftButton)
QTimer.singleShot(250,accept_assistant); w.auto_mesh()
deadline=time.time()+180
while True:
    w.poll(); QTest.qWait(150)
    if not w.preview_job_id and any(j['name'].startswith('OFF_ASSISTANT_'+tag) and j['state']=='DONE' for j in w.jobs): break
    if errors: raise RuntimeError(errors)
    if time.time()>deadline: raise TimeoutError('Assistant preview / automatic display timed out')
assert w.tabs.currentIndex()==1; assert w.viewer.result.internal.GetNumberOfCells()==5120; w.viewer.slice.setCurrentIndex(w.viewer.slice.findData('XY mid-slice')); w.viewer.fit(); w.viewer.image().save(out/'guided_mesh_preview.png')
j=next(j for j in w.jobs if j['name'].startswith('OFF_ASSISTANT_'+tag)); captured['ogrid_preview']={'case':j['name'],'cells':j['quality']['cells'],'skewness':j['quality']['skewness'],'nonorthogonality':j['quality']['non_orthogonality'],'state':j['state']}
# Format/save only whitespace in a completed real case; validate with OpenFOAM.
completed=next(j for j in w.jobs if j['name']==json.loads((out/'validation.json').read_text())['rounds'][0]['case'])
dlg=DictionaryDialog(completed['case'],lambda:True,w); dlg.show(); QTest.qWait(100); original_tokens=tokens(dlg.current.read_text()); assert tokens(dlg.editor.toPlainText())==original_tokens; assert dlg.check(); dlg.save_current(); assert tokens(dlg.current.read_text())==original_tokens
parsed=wsl(Profile(),f"source /opt/openfoam14/etc/bashrc >/dev/null 2>&1; foamDictionary '{completed['linux_case']}/system/fvSolution' -entry PIMPLE/nOuterCorrectors -value")
assert parsed.returncode==0 and parsed.stdout.strip()=='2',parsed.stderr
dlg.grab().save(str(out/'dictionary_editor_EN.png')); dlg.close()
# A translated dialog and canonical choices; confirm actual website action URL.
w.change_language('zh'); dlg=DictionaryDialog(completed['case'],lambda:False,w); dlg.show(); QTest.qWait(100); assert dlg.editor.isReadOnly(); dlg.grab().save(str(out/'dictionary_editor_ZH.png')); dlg.close()
assistant=MeshAssistant(w.project,w); assistant.show(); QTest.qWait(100); assistant.grab().save(str(out/'mesh_assistant_ZH.png')); assistant.close()
urls=[]; old=QDesktopServices.openUrl; QDesktopServices.openUrl=lambda url:(urls.append(url.toString()) or True)
website=next(a for a in w.findChildren(__import__('PySide6.QtGui',fromlist=['QAction']).QAction) if a.property('off_original')=='Website support'); website.trigger(); QDesktopServices.openUrl=old; assert urls==['http://spaceaero.space']
w.tabs.setCurrentIndex(0); w.canvas.fit(); w.grab().save(str(out/'workspace_ZH.png'))
# Genuine Gmsh assistant size regions and 2D conversion; strict gate is preserved.
p=Project(name='OFF_ASSISTED_GMSH_'+tag,dimension=2); assistant=MeshAssistant(p,w); assistant.method.setCurrentIndex(assistant.method.findData('Gmsh triangle / prism')); p=assistant.project(); assert len(p.regions)==2 and p.skew_limit==.5 and p.nonortho_limit==30.; g=w.engine.enqueue(p,mesh_only=True)
deadline=time.time()+180
while True:
    g=next(j for j in w.engine.tick() if j['id']==g['id'])
    if g['state'] in ('DONE','FAILED'): break
    if time.time()>deadline: raise TimeoutError('Unstructured assistant mesh timed out')
    QTest.qWait(150)
assert g['state']=='DONE',g['quality']
captured['unstructured_preview']={'case':g['name'],'regions':len(p.regions),'cells':g['quality']['cells'],'skewness':g['quality']['skewness'],'nonorthogonality':g['quality']['non_orthogonality'],'strict_gate':True,'state':g['state']}
report={'bilingual_switch_passed':True,'canonical_values_preserved':True,'draw_undo_redo_duplicate_delete_passed':True,'dictionary_token_preservation':True,'openfoam_parser_after_formatted_save':parsed.stdout.strip(),'website_action_url':urls[0],'website_network_access_not_asserted':True,'real_previews':captured,'errors':errors}
(out/'upgrade_validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
while w.workers: QTest.qWait(50)
w.close()
