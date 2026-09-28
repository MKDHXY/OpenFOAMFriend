import os,sys,json,subprocess,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'installer'));import install_core as core
PACK=BASE.parent/'packages'/BASE.name;E=BASE/'evidence/package_QA';rows=[]
for mode in ('full','lite'):
    folder=PACK/('OpenFoamFriend_'+mode.upper()+'_'+BASE.name);core.verify_bundle(folder)
    runtime=folder/'runtime/python.exe'
    code='import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import off.ssh_backend as s;from off.models import Profile;import gmsh,vtk,PySide6;gmsh.initialize();gmsh.finalize();assert Path(s.client_executable("ssh")).is_file();print(s.client_executable("ssh"));assert Profile().distro=="OpenFoamFriend-14"'
    output=core.run([runtime,'-X','utf8','-c',code,folder/'application'/BASE.name],90)
    version=core.run([folder/'runtime/tools/openssh/ssh.exe','-V']);assert 'OpenSSH' in version or version==''
    gui=core.run([runtime,'-X','utf8',folder/'application'/BASE.name/'tests/validate_welcome_package.py'],90)
    assert 'PASS' in gui
    rows.append(dict(mode=mode,manifest_verified=True,isolated_runtime_imports=True,bundled_SSH_client_exists=True,actual_welcome_in_staged_app=gui.strip(),runtime=str(runtime)))
# Verify profile configuration and actual installer entrypoint from final source.
full=PACK/('OpenFoamFriend_FULL_'+BASE.name);target=BASE.parent/'installer_cache/Installed FULL 中文 space'
record=core.install(full,target,'OFFPackageInstallerQA_20260928_164718',make_shortcuts=False,configure_profile=True)
profile=json.loads((Path(os.environ['APPDATA'])/'OpenFoamFriend/profile.json').read_text());assert profile['distro']==record['distro'] and profile['run_dir']=='/home/off/OpenFOAM/off14/run' and profile['max_cores']==4
assert list((Path(os.environ['APPDATA'])/'OpenFoamFriend').glob('profile.before_install_*.json'))
final=dict(rows=rows,final_full_installer_with_profile_verified=True,existing_profile_backup=True,full_record=record)
(E/'final_bundle_validation.json').write_text(json.dumps(final,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(final,indent=2,ensure_ascii=False),flush=True)
