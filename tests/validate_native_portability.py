import sys,json,tempfile,os
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QValidator
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from off.numeric_controls import ScientificSpin
from off.workspace_tools import export_case
from off.post import Result
from off.backend import Engine,JobStore
from off.models import Profile
app=QApplication([]); spin=ScientificSpin(); spin.setRange(0,1e9); spin.show(); spin.lineEdit().setText('7.5e-8'); spin.interpretText(); assert abs(spin.value()-7.5e-8)<1e-20; assert spin.text()=='7.5e-08'; before=spin.value(); spin.stepUp(); assert 0<spin.value()-before<1e-6
assert spin.validate('nan',3)[0]==QValidator.Invalid
for i in range(100): assert spin.validate('1e-8',4)[0]==QValidator.Acceptable
assert len(spin.findChildren(__import__('PySide6.QtGui',fromlist=['QDoubleValidator']).QDoubleValidator))==1
native=json.loads((BASE/'evidence/native_runtime_validation.json').read_text()); source=Path(native['models'][0]['case'])
with tempfile.TemporaryDirectory() as root:
    destination=Path(root)/'native_case'; metadata=export_case(next(source.glob('*.foam')),destination); assert metadata['native_model_sources']
    assert (destination/'off_native/dynamicLagrangian/COPYING').exists() and not (destination/'off_native/dynamicLagrangian/lnInclude').exists()
    r=Result(metadata['marker']); assert len(r.times)==3 and r.internal.GetNumberOfCells()==5120
# Re-read one retained real compilation failure: the queue must show preparation diagnostics.
initial=json.loads((BASE/'evidence/model_runtime_first_attempt_current_release.json').read_text()); db=BASE/'data'/('model_tests_'+initial['attempt']+'.sqlite'); engine=Engine(Profile(),JobStore(db)); job=next(j for j in engine.store.all() if j['project']['turbulence']=='dynamicLagrangian'); job.pop('log_tail',None); engine.store.save(job); fresh=next(j for j in engine.tick() if j['id']==job['id']); assert fresh['state']=='FAILED' and 'missing separator' in fresh['log_tail']
assert b'\r\n' not in (source/'off_native/dynamicLagrangian/Make/files').read_bytes()
report={'scientific_input_and_adaptive_step':True,'validator_reused':True,'native_complete_case_export_reopened':True,'native_source_license_retained_build_artifacts_excluded':True,'actual_compile_failure_diagnostics_visible':True,'errors':[]}; (BASE/'evidence/native_portability_validation.json').write_text(json.dumps(report,indent=2)); spin.close(); print(report)
