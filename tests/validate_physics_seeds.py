import sys,json,tempfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools'))
from off.models import Project,Profile
from off.backend import write_case
from cycle_ledger import record
for key in ('velocity','viscosity','turbulence_intensity','turbulence_length','dynamic_seed','transition_retheta','max_co'):
    p=Project(); setattr(p,key,float('nan'))
    try: p.validate(); raise AssertionError(key)
    except ValueError: pass
with tempfile.TemporaryDirectory() as root:
    path=write_case(Project(turbulence='kOmegaSSTLM',transition_retheta=160.99,intermittency=.4),Profile(),Path(root)/'lm')
    assert '160.99' in (path/'0/ReThetat').read_text() and '0.4' in (path/'0/gammaInt').read_text()
    path=write_case(Project(turbulence='SpalartAllmaras',sa_viscosity_ratio=7),Profile(),Path(root)/'sa'); assert '0.035' in (path/'0/nuTilda').read_text()
report={'nonfinite_inputs_rejected':True,'transition_and_SA_seeds_propagate':True,'backward_compatible_schema':1,'errors':[]}; (BASE/'evidence/physics_seeds_validation.json').write_text(json.dumps(report,indent=2)); record(6,'New transition and SA models need explicit problem-dependent seeds; NaN bypassed simple positive comparisons.','Expose transition ReThetat/intermittency, SA viscosity ratio and dynamic seed, disable irrelevant controls, reject nonfinite numeric project values.','Generate customised transition/SA fields and reject NaN in seven important parameters.','physics_seeds_validation.json'); print(report)
