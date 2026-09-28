"""Actual sketch / monotone formulas / dictionary parsing; mocked SSH transport only."""
import os,sys,time,json,tempfile,tarfile,copy
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from off.gui import MainWindow
from off.models import Project,host_path,linux_case_path
from off.backend import DATA,BASE,write_case,wsl
from off.grading import cell_widths,size_expression,GradingDialog
from off.ssh_backend import Cluster,batch_script,bundle,ssh_args
from off.ssh_gui import SSHDialog
from off.dictionary_editor import DictionaryDialog,format_foam
app=QApplication([]); (BASE/'evidence').mkdir(exist_ok=True); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append; QTest.qWait(400)
c=w.canvas; c.set_tool('line'); a=c.mapFromScene(-100,-100); b=c.mapFromScene(0,-100)
QTest.mousePress(c.viewport(),Qt.LeftButton,pos=a); QTest.mouseMove(c.viewport(),b); QTest.mouseRelease(c.viewport(),Qt.LeftButton,pos=b); assert len(w.project.curves)==1; assert abs(w.project.curves[0]['points'][0][1]-w.project.curves[0]['points'][1][1])<1e-12
c.undo(); assert not w.project.curves; c.redo(); assert len(w.project.curves)==1
c.set_tool('polyline')
for p in [a,b,c.mapFromScene(0,0)]: QTest.mouseClick(c.viewport(),Qt.LeftButton,pos=p)
QTest.keyClick(c,Qt.Key_Return); assert len(w.project.curves)==2; assert len(w.project.curves[-1]['points'])==3
w.project.save(DATA/'curves.off.json'); assert Project.load(DATA/'curves.off.json').curves==w.project.curves
widths=cell_widths(9.5,20,4); assert all(b>a for a,b in zip(widths,widths[1:])); assert abs(sum(widths)-9.5)<1e-12; assert abs(widths[-1]/widths[0]-4)<1e-12
assert cell_widths(9.5,20,.25)==list(reversed(widths)) or all(abs(a-b)<1e-12 for a,b in zip(cell_widths(9.5,20,.25),reversed(widths)))
r={'direction':'x-','ratio':4,'x':-2,'y':-1,'width':4,'height':2,'size':.1}; expr=size_expression(r)
def evaluate(x): return eval(expr.replace('^','**'),{'__builtins__':{}},{'x':x,'Abs':abs})
assert evaluate(2)==1 and evaluate(-2)==4
g=GradingDialog(w.project,w); g.mode.setCurrentIndex(2); g.ratio.setValue(4); g.apply(); assert w.project.grading==.25
stamp=time.strftime('%Y%m%d_%H%M%S'); p=Project(name='OFF_EDIT_'+stamp); draft=write_case(p,w.profile,DATA/('draft_test_'+stamp)); override=__import__('re').sub(r'(internalField\s+uniform\s*\()\s*1\.0',r'\g<1> 0.9',format_foam((draft/'0/U').read_text())); assert '0.9' in override; p.dictionary_overrides={'0/U':override}; case=write_case(p,w.profile)
result=wsl(w.profile,'source '+w.profile.bashrc+' >/dev/null 2>&1; foamDictionary '+linux_case_path(w.profile,p.name)+'/0/U -entry internalField -value'); assert result.returncode==0 and '0.9' in result.stdout
dialog=DictionaryDialog(case,lambda:True,w,preferred='0/U'); assert dialog.current.name=='U'; dialog.close()
cluster=Cluster(host='example-cluster',user='researcher',remote_root='/scratch/researcher/off'); args=ssh_args(cluster); assert 'StrictHostKeyChecking=yes' in args and 'BatchMode=yes' in args; script=batch_script(cluster,p.name); assert '#SBATCH --ntasks=4' in script and 'srun foamRun' in script
from off.mesh import cylinder_dict
(case/'system/blockMeshDict').write_text(cylinder_dict(p)); archive=DATA/'ssh_test.tar.gz'; bundle(case,script,archive)
with tarfile.open(archive) as f: assert {'0/U','0/p','system/blockMeshDict','submit.slurm'}<=set(f.getnames()); assert not any(v.startswith('processor') for v in f.getnames())
(DATA/'submit_test.slurm').write_text(script,encoding='utf-8',newline='\n')
syntax=wsl(w.profile,'bash -n /mnt/d/UoM/openfoamfriend/'+BASE.name+'/data/submit_test.slurm'); assert syntax.returncode==0,syntax.stderr
remote=SSHDialog(w); remote.show(); QTest.qWait(50); remote.grab().save(str(BASE/'evidence/ssh_EN.png')); remote.close()
w.tabs.setCurrentIndex(2); assert not w.sketch_toolbar.isVisible(); w.tabs.setCurrentIndex(0); c.fit(); w.grab().save(str(BASE/'evidence/professional_EN.png'))
report={'construction_line_polyline_pointer_test':True,'undo_redo_serialization':True,'monotone_spacing_formula':True,'negative_direction_endpoints':True,'initial_U_verified_by_foamDictionary':result.stdout.strip(),'SSH_host_key_enforced':True,'Slurm_script_bash_syntax':True,'SSH_bundle_verified':True,'real_cluster_tested':False,'remote_job_submitted':False,'errors':errors}; assert not errors
(BASE/'evidence/professional.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2))
while w.workers: QTest.qWait(100)
w.close()
