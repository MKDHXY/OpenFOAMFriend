"""Read-only installation check; does not start or alter a CFD case."""
import sys,json,platform,importlib,importlib.metadata
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
packages={'PySide6':'PySide6','vtk':'vtk','gmsh':'gmsh','numpy':'numpy','scipy':'scipy','matplotlib':'matplotlib','Pillow':'PIL'}
result={'python':sys.version,'architecture':platform.architecture()[0],'dependencies':{}}
for name,module in packages.items():
    importlib.import_module(module); result['dependencies'][name]=importlib.metadata.version(name)
assert platform.architecture()[0]=='64bit','64-bit Python is required.'
if '--wsl' in sys.argv:
    from off.models import load_profile
    from off.backend import probe
    result['wsl_probe']=probe(load_profile())
print(json.dumps(result,indent=2)); print('Runtime imports OK. Use --wsl after configuring the machine profile to test OpenFOAM.')
