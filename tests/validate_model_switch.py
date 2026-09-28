import sys,os,json,tempfile,tarfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools')); os.environ['OFF_LANGUAGE']='en'
from PySide6.QtWidgets import QApplication,QCheckBox
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from off.gui import MainWindow
from off.models import Project,Profile
from off.backend import write_case
from off.ssh_backend import Cluster,bundle,batch_script
from off.i18n import set_language
from cycle_ledger import record
app=QApplication([]); w=MainWindow(); w.timer.stop(); errors=[]; w.error=errors.append
while w.workers: QTest.qWait(20)
with tempfile.TemporaryDirectory() as root:
    baseline=write_case(Project(turbulence='kOmegaSST'),Profile(),Path(root)/'baseline')
    p=Project(turbulence='kOmegaSST'); p.dictionary_overrides={'0/omega':(baseline/'0/omega').read_text(),'0/U':(baseline/'0/U').read_text()}; p.validate(); p.turbulence='WALE'
    try: p.validate(); raise AssertionError('Stale omega override accepted')
    except ValueError: pass
    w.project=Project(turbulence='kOmegaSST',dictionary_overrides=p.dictionary_overrides.copy()); w.canvas.project=w.project
    def switch():
        d=app.activeModalWidget(); d.inputs['turbulence'].setCurrentIndex(d.inputs['turbulence'].findData('WALE'))
        reset=next(b for b in d.findChildren(QCheckBox) if 'Reset model-specific' in b.text()); assert not reset.isChecked(); reset.setChecked(True); d.accept()
    QTimer.singleShot(150,switch); w.flow_settings(); assert w.project.turbulence=='WALE' and set(w.project.dictionary_overrides)=={'0/U'} and not errors
    # Packaging must retain native source and licence for another WSL/cluster host.
    dynamic=write_case(Project(turbulence='dynamicLagrangian'),Profile(),Path(root)/'dynamic')
    from off.mesh import cylinder_dict
    (dynamic/'system/blockMeshDict').write_text(cylinder_dict(Project()))
    script=batch_script(Cluster(host='test-host'),dynamic.name); assert 'wmake libso off_native/dynamicLagrangian' in script
    archive=Path(root)/'upload.tar.gz'; bundle(dynamic,script,archive)
    with tarfile.open(archive) as t: assert 'off_native/dynamicLagrangian/COPYING' in t.getnames() and 'off_native/dynamicLagrangian/offDynamicLagrangian.C' in t.getnames()
report={'stale_model_override_rejected_before_case_creation':True,'explicit_optional_reset_preserves_U':True,'SSH_native_source_license_and_compile_step':True,'errors':errors}; (BASE/'evidence/model_switch_validation.json').write_text(json.dumps(report,indent=2)); record(10,'Switching physics could retain incompatible omega/k dictionary overrides; an isolated native model needs portable source/build support rather than a host-only binary.','Reject stale model-field overrides early; offer an unchecked explicit reset retaining U/p/viscosity; retain native GPL sources in complete-case/SSH exports and compile them on the target host.','Real model dialog switch with explicit reset, stale-field rejection, and SSH archive/compile-script checks; follow with complete additive-feature regression suite.','model_switch_validation.json; regression_fast.json; final_regression_validation.json'); w.close(); print(report)
