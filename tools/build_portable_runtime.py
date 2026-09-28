from pathlib import Path
import zipfile,subprocess,sys,shutil
root=Path(__file__).resolve().parents[2];runtime=root/'installer_cache'/'portable_runtime';runtime.mkdir(exist_ok=True)
with zipfile.ZipFile(root/'installer_cache/python-3.12.10-embed-amd64.zip') as z:z.extractall(runtime)
(runtime/'python312._pth').write_text('python312.zip\n.\nLib/site-packages\n')
subprocess.run([sys.executable,'-m','pip','install','--no-index','--find-links',str(root/'installer_cache/wheels'),'--target',str(runtime/'Lib/site-packages'),'-r','requirements.txt'],check=True)
with zipfile.ZipFile(root/'installer_cache/wheels/gmsh-4.15.2-py2.py3-none-win_amd64.whl') as z:
 for name in z.namelist():
  if name.lower().endswith('.dll'):(runtime/'Lib/site-packages'/Path(name).name).write_bytes(z.read(name))
for pattern in ('msvcp*.dll','vcruntime*.dll','concrt*.dll'):
 for library in (runtime/'Lib/site-packages/PySide6').glob(pattern):shutil.copy2(library,runtime/library.name)
print('Portable embedded runtime prepared')
