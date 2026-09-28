"""Real relocation/app copy/Linux import, with isolated recipient settings."""
import sys,json,os,shutil,hashlib,subprocess
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'installer'))
import install_core as core
CACHE=BASE.parent/'installer_cache';PACKAGES=BASE.parent/'packages'/BASE.name;out=BASE/'evidence/package_QA';out.mkdir(parents=True,exist_ok=True)
assert all('Roaming' not in p and 'software' not in p for p in sys.path)
checks=[]
full=PACKAGES/('OpenFoamFriend_FULL_'+BASE.name);lite=PACKAGES/('OpenFoamFriend_LITE_'+BASE.name)
# Real full installer invokes the actual offline import against a new distro.
target=CACHE/'Installed FULL 中文 space';name='OFFPackageInstallerQA_20260928_164718'
record=core.install(full,target,name,progress=lambda s:print(s,flush=True),make_shortcuts=False,configure_profile=False)
assert record['environment']['ready'] and record['environment']['user']=='off';checks.append('Full actual import + relocated bundled runtime PASS')
full_runtime=core.run([target/'runtime/python.exe','-X','utf8','-c','import sys,gmsh,PySide6,vtk;gmsh.initialize();gmsh.finalize();assert all("Roaming" not in p and "software" not in p for p in sys.path);print(sys.executable);print(sys.path)'],90)
# Inject missing WSL to prove Lite does not attempt any installation; keep actual copying/runtime checks.
saved_environment=core.environment;commands=[];saved_run=core.run
core.environment=lambda *a,**k:dict(ready=False,wsl_present=False,errors=['WSL missing'],distributions=[])
def tracked(args,timeout=60):
    commands.append([str(a) for a in args]);assert Path(str(args[0])).name=='python.exe',args
    return saved_run(args,timeout)
core.run=tracked
lite_target=CACHE/'Installed LITE 中文 space';lr=core.install(lite,lite_target,progress=lambda s:print(s,flush=True),make_shortcuts=False,configure_profile=True)
assert lr['installed'] and not lr['environment']['ready'];assert not (lite_target/'wsl').exists();assert not (lite/'payload').exists();checks.append('Lite missing WSL: no Linux/system commands PASS')
core.run=saved_run;core.environment=saved_environment
# Managed-directory protection, invalid distro/mode, checksum rejection.
protected=CACHE/'unrelated protected folder';protected.mkdir(exist_ok=True);(protected/'keep.txt').write_text('keep me')
try:core.install(lite,protected,make_shortcuts=False)
except FileExistsError:checks.append('Nonempty unrelated directory protected PASS')
else:raise AssertionError('Unmanaged target was not protected')
assert (protected/'keep.txt').read_text()=='keep me'
corrupt=CACHE/'corrupt QA manifest';corrupt.mkdir(exist_ok=True);(corrupt/'a.txt').write_text('wrong');(corrupt/'bundle_manifest.json').write_text(json.dumps({'sha256':{'a.txt':'0'*64}}))
try:core.verify_bundle(corrupt)
except RuntimeError:checks.append('Corrupt payload rejected PASS')
else:raise AssertionError('Bad hash accepted')
# Read-only Windows-stage entry, actual PowerShell parse and correct Lite rejection.
ps=core.run(['powershell.exe','-NoProfile','-File',full/'installer/prepare_windows.ps1','-Bundle',full,'-InspectOnly'])
assert 'no forced restart' in ps
from unittest.mock import patch
with patch.object(core.shutil,'which',return_value=None),patch.object(Path,'exists',return_value=False):assert not core.environment()['ready']
checks.append('Read-only missing WSL diagnostic PASS')
result=dict(release=BASE.name,checks=checks,full_record=record,lite_record=lr,lite_actual_commands=commands,isolated_runtime=full_runtime,windows_stage_inspect_only=ps,cold_windows_feature_enable_and_reboot_physically_tested=False,system_python_not_on_PATH=True)
(out/'offline_install_validation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
