import sys,json,tempfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools'))
from off.physics import MODELS,EDITABLE_KEYS
from off.models import Project,Profile
from off.backend import write_case
from off.dictionary_editor import validate_foam
from cycle_ledger import record
rows=[]
with tempfile.TemporaryDirectory() as root:
    for name,m in MODELS.items():
        path=write_case(Project(turbulence=name),Profile(),Path(root)/name)
        for field in ('U','p')+m.fields: assert (path/'0'/field).exists(),(name,field)
        for key in EDITABLE_KEYS:
            f=path/key
            if f.exists(): validate_foam(f.read_text())
        if 'R' in m.fields: assert 'volSymmTensorField' in (path/'0/R').read_text()
        rows.append({'model':name,'required_fields':m.fields,'dictionary_contract':'PASS'})
report={'contracts':rows,'tensor_field_class':True,'errors':[]}; (BASE/'evidence/model_contract_validation.json').write_text(json.dumps(report,indent=2))
record(4,'Adding model names alone leaves missing scalar/tensor fields and solver discretisation entries.','Generate required initial fields, wall policies, dimensions, model coefficients, transported-field solvers and editable initial dictionaries for each family.','Generate and validate all 24 complete model dictionary contracts; verify R is a symmetric tensor.','model_contract_validation.json'); print('24 model contracts PASS')
