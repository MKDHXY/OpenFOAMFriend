"""Public CI: pure contracts; no fabricated CFD execution."""
import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from off.models import Project,Profile
from off.physics import MODELS
from off.manual_topology import cylinder_preset,validate,block_dict
from off.ssh_backend import Cluster,batch_script
assert Project().dimension==3 and Project().cores==4
assert Profile().distro=='OpenFoamFriend-14'
assert len(MODELS)==24 and 'kOmegaSST' in MODELS and 'laminar' in MODELS
p=Project();p.validate()
with tempfile.TemporaryDirectory() as root:
    f=Path(root)/'project.off.json';p.save(f);assert Project.load(f)==p
graph=cylinder_preset();validate(graph,'blockMesh');assert 'blocks' in block_dict(Project(mesh_method='Manual topology (blockMesh)',manual_mesh=graph))
c=Cluster(host='example.invalid',user='researcher');script=batch_script(c,'Smoke');assert '#SBATCH --ntasks=4' in script and 'foamRun' in script
assert not any(key in script for key in ('StrictHostKeyChecking=no','password='))
print(json.dumps({'pure_contracts':'PASS','CFD_executed':False,'model_count':len(MODELS)}))

