import sys,json,subprocess,re
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools'))
from off.physics import MODELS
from cycle_ledger import record
r=subprocess.run(['wsl','-d','Ubuntu','--','cat','/opt/openfoam14/src/MomentumTransportModels/incompressible/incompressibleMomentumTransportModels.C'],capture_output=True,text=True,check=True)
ras=re.findall(r'makeRASModel\((\w+)\)',r.stdout); les=re.findall(r'makeLESModel\((\w+)\)',r.stdout)
assert set(ras+les)==set(MODELS)-{'laminar'},(ras,les)
report={'registered_RAS':ras,'registered_LES_and_hybrid':les,'catalogue_count':len(MODELS),'matches_installed_factory':True,'errors':[]}
(BASE/'evidence/model_catalogue_validation.json').write_text(json.dumps(report,indent=2))
record(3,'The physics selector exposed only laminar and SST, omitting registered mainstream families.','Add a typed catalogue of 24 options: laminar, 13 RAS, 6 LES and 4 hybrid DES/DDES/IDDES; document field requirements and scientific scope.','Compare every catalogue model against the installed Foundation 14 factory registrations.','model_catalogue_validation.json'); print(report)
