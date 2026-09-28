"""Five sequential targeted QA stages; preserves preferences and real evidence."""
import sys,os,json,time,copy,hashlib,shutil,argparse,math
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from off.models import Project
from off.reynolds import reynolds,reference,solve
from off.reynolds_gui import ReynoldsDialog
from off import i18n
app=QApplication([])
parser=argparse.ArgumentParser(); parser.add_argument('cycle',type=int); args=parser.parse_args(); cycle=args.cycle; proof={}
prefs=copy.deepcopy(i18n.preferences()); errors=[]
try:
    if cycle==1:
        from off.gui import MainWindow
        w=MainWindow(); w.show(); w.timer.stop()
        while w.workers: QTest.qWait(20)
        w.set_guided(False); assert w.mode_combo.currentData() is False and w.expert_button.isEnabled()
        w.mode_combo.setCurrentIndex(1); assert w.guide_action.isChecked() and not w.expert_button.isEnabled()
        w.mode_combo.setCurrentIndex(0); assert not w.guide_action.isChecked()
        p=Project(); d=ReynoldsDialog(p,w); d.show(); QTest.qWait(50); d.inputs['target'].setValue(3900); d.calculate('viscosity'); d.accept()
        assert math.isclose(reynolds(d.result_project.velocity,reference(d.result_project)[0],d.result_project.viscosity),3900)
        assert p.viscosity==.005 and d.result_project.shapes==p.shapes
        d=ReynoldsDialog(p,w); d.inputs['target'].setValue(1e7); d.calculate('velocity'); d.reject(); assert p.velocity==1
        w.grab().save(str(BASE/'evidence/expert_mode.png')); w.close(); proof={'expert_entry_visible':True,'mode_switch_synchronised':True,'Re3900_calculate_nu':True,'cancel_and_geometry_unchanged':True}
    elif cycle==2:
        for target in (1,10,40,100,200,1200,3900,1e4,1e5,1e6,1e7):
            for u,length,nu in ((.015,.001,7.5e-8),(1,1,.005),(100,.0001,1e-6)):
                assert math.isclose(reynolds(u,length,solve(target,u,length,nu,'viscosity')),target,rel_tol=1e-12)
                assert math.isclose(reynolds(solve(target,u,length,nu,'velocity'),length,nu),target,rel_tol=1e-12)
        d=ReynoldsDialog(Project()); d.inputs['target'].setValue(1e7); d.calculate('viscosity'); d.accept(); assert math.isclose(d.result_project.viscosity,1e-7)
        custom=Project(reference_length=.002); assert reference(custom)==(.002,'custom')
        try: reference(Project(shapes=[])); raise AssertionError('missing reference silently guessed')
        except ValueError: pass
        proof={'SI_endpoint_and_scaling_combinations':66,'Re1_to_1e7':True,'missing_reference_rejected':True,'custom_L_explicit':True}
    elif cycle in (3,4,5):
        from off.advisor import recommend
        p=Project(); a=recommend(p); assert a['re']==200 and a['preferred_model']=='laminar'
        p=Project(viscosity=1/3900); a=recommend(p); assert a['preferred_model']=='kOmegaSST'
        p.dimension=2; a=recommend(p); assert any(r['code']=='cylinder_3d' for r in a['messages'])
        p.dimension=3; p.spanwise=4; p.turbulence='WALE'; a=recommend(p); assert any(r['code']=='les_resolution' for r in a['messages'])
        p.viscosity=1e-7; a=recommend(p); assert a['re']==1e7 and any(r['code']=='high_re' for r in a['messages'])
        q={'max_skewness':.9,'max_nonorthogonality_deg':55,'nonpositive_cells':0,'cells':5120}; a=recommend(p,q); assert any(r['code']=='mesh_quality' for r in a['messages'])
        q['nonpositive_cells']=1; a=recommend(p,q); assert a['blocked']
        proof={'model_advice_and_scope_guards':True,'Re1e7_no_automatic_LES':True,'actual_quality_thresholds':True}
        if cycle>=4:
            from off.advisor_gui import AdviceDialog
            d=AdviceDialog(Project(),None); d.show(); QTest.qWait(80); assert not d.apply_button.isEnabled(); assert 'unknown' in d.report.toPlainText().lower(); d.close()
            d=ReynoldsDialog(Project(dictionary_overrides={'0/U':'FoamFile { format ascii; class volVectorField; object U; } internalField uniform (1 0 0);'})); d.inputs['target'].setValue(3900); d.calculate('viscosity'); d.accept(); assert d.result_project is None
            d.reset_overrides.setChecked(True); d.accept(); assert '0/U' not in d.result_project.dictionary_overrides
            proof['dictionary_override_conflict_and_explicit_reset']=True
            good={'max_skewness':.01,'max_nonorthogonality_deg':.1,'nonpositive_cells':0,'cells':5120}
            assert recommend(Project(),good,speed_of_sound=1)['blocked']
            assert not recommend(Project(),good,speed_of_sound=340)['blocked']
            bad=dict(good,max_skewness=float('nan')); assert recommend(Project(),bad)['blocked']
        if cycle==5:
            native=json.loads((BASE/'evidence/native_runtime_validation.json').read_text()); assert native['all_selected_passed']
            build_file=Path(native['models'][0]['case'])/'off_native/dynamicLagrangian/Make/files'; assert b'\r\n' not in build_file.read_bytes()
            proof['cold_native_build_LF_portability']=True
            from off.gui import MainWindow
            w=MainWindow(); w.show(); w.timer.stop()
            while w.workers: QTest.qWait(20)
            w.set_guided(False); w.resize(1100,740); QTest.qWait(100); assert w.mode_widget.width()<w.width()*.6
            w.grab().save(str(BASE/'evidence/expert_advisor_workbench.png')); w.change_language('zh'); assert w.mode_combo.itemText(0)=='专家模式' and w.mode_label.text()=='工作方式：'; w.grab().save(str(BASE/'evidence/expert_advisor_workbench_ZH.png')); w.close()
            d=ReynoldsDialog(Project(velocity=.015,viscosity=7.5e-8,shapes=[{'kind':'circle','x':0,'y':0,'width':.001,'height':.001,'name':'cylinder'}])); d.show(); QTest.qWait(80); d.grab().save(str(BASE/'evidence/reynolds_dialog.png')); d.close()
except Exception as e:
    errors.append(str(e)); raise
finally:
    for k,v in prefs.items(): i18n.save_preference(k,v)
    record={'cycle':cycle,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'proof':proof,'errors':errors,'result':'PASS' if not errors else 'FAIL'}
    (BASE/'evidence'/f'reynolds_cycle_{cycle}.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
