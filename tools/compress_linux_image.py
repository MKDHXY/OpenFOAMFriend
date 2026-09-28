import gzip,shutil,hashlib,json,time
from pathlib import Path
cache=Path(__file__).resolve().parents[2]/'installer_cache'
source=cache/'openfoam14-ubuntu24.04.tar';target=source.with_suffix('.tar.gz')
print('Compressing clean root filesystem',source.stat().st_size,flush=True)
with source.open('rb') as inp,gzip.open(target,'wb',compresslevel=3) as out:shutil.copyfileobj(inp,out,8*1024*1024)
with target.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
(cache/'clean_image.json').write_text(json.dumps(dict(file=target.name,bytes=target.stat().st_size,sha256=h,created=time.strftime('%Y-%m-%d %H:%M:%S'),build_distro='OFFPackageBuild_20260928_164718'),indent=2))
print('Clean image',target.stat().st_size,h,flush=True)
