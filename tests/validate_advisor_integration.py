"""Actual current-release mesh -> advice -> deliberate model application."""
import sys,os,json,time,copy,math,tempfile
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from off.models import Project,Profile
from off.gui import MainWindow
from off.advisor_gui import AdviceDialog
from off.advisor import mesh_signature,recommend
from off.meshmetrics import measure
from off.backend import write_case
app=QApplication([]); v=json.loads((BASE/'evidence/validation.json').read_text()); case=Path(v['rounds'][0]['case_folder'])
quality,metrics=measure(case); assert quality['cells']==5120 and metrics['uniform_flux_rate_per_velocity']>0
assert 0<metrics['wall_cell_distance']['min_m']<.1
p=Project(name='Advice_Re3900',viscosity=1/3900); a=recommend(p,quality,metrics); assert a['preferred_model']=='kOmegaSST'; assert a['estimated_start_dt_s']>0
assert math.isclose(a['estimated_start_dt_s'],p.max_co/(p.velocity*metrics['uniform_flux_rate_per_velocity']))
assert mesh_signature(p)==mesh_signature(Project())
w=MainWindow(); w.timer.stop(); w.error=lambda e:(_ for _ in ()).throw(AssertionError(e)); w.project=p; w.canvas.project=p; w.refresh_tree(); w.show()
while w.workers: app.processEvents(); time.sleep(.02)
proof={}; timer=QTimer(); timer.setInterval(100)
def accept_advice():
    dialog=app.activeModalWidget()
    if not isinstance(dialog,AdviceDialog): return
    timer.stop(); assert dialog.evidence and dialog.evidence['quality']['cells']==5120
    assert dialog.evidence['mesh_signature']==mesh_signature(p); assert not dialog.apply_button.isEnabled()
    dialog.review.setChecked(True); assert dialog.apply_button.isEnabled(); dialog.grab().save(str(BASE/'evidence/setup_advice.png')); dialog.apply(); proof['matched_real_mesh_and_explicit_model_apply']=True
timer.timeout.connect(accept_advice); timer.start(); w.setup_advice(); deadline=time.time()+30
while w.workers or not proof:
    app.processEvents(); time.sleep(.02)
    if time.time()>deadline: raise TimeoutError('Advice integration exceeded 30s')
assert w.project.turbulence=='kOmegaSST' and w.project.viscosity==p.viscosity and w.project.shapes==p.shapes and w.project.delta_t==p.delta_t
w.project.radial+=1; w.canvas.project=w.project; w.refresh_tree()
def reject_stale():
    dialog=app.activeModalWidget()
    if not isinstance(dialog,AdviceDialog): return
    assert dialog.evidence is None and not dialog.apply_button.isEnabled(); dialog.reject(); proof['geometry_change_invalidates_old_mesh']=True
QTimer.singleShot(100,reject_stale); w.setup_advice(); assert proof['geometry_change_invalidates_old_mesh']
with tempfile.TemporaryDirectory() as temp:
    custom=Project(name='ScaleCustom',reference_length=.002); generated=write_case(custom,Profile(),Path(temp)/'custom'); control=(generated/'system/controlDict').read_text(); assert 'lRef 0.002' in control
    destination=Path(temp)/'invalid'
    try: write_case(Project(shapes=[]),Profile(),destination); raise AssertionError('Ambiguous scale accepted')
    except ValueError: assert not destination.exists()
proof.update({'real_mesh_metrics':metrics,'no_geometry_or_time_mutation':True,'custom_force_length_consistent':True,'bad_reference_creates_no_case':True,'errors':[]})
(BASE/'evidence/advisor_integration.json').write_text(json.dumps(proof,indent=2),encoding='utf-8'); print(json.dumps(proof,indent=2)); w.close()
