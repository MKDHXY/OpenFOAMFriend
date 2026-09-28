import urllib.request,json,hashlib
from pathlib import Path
cache=Path(__file__).resolve().parents[2]/'installer_cache/component_sources';cache.mkdir(exist_ok=True)
urls=['https://gmsh.info/src/gmsh-4.15.2-source.tgz','https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz']
rows=[]
for url in urls:
    p=cache/url.rsplit('/',1)[-1]
    if not p.exists():
        with urllib.request.urlopen(url,timeout=90) as r,p.open('wb') as out:
            while chunk:=r.read(1024*1024):out.write(chunk)
    with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    rows.append(dict(url=url,file=p.name,bytes=p.stat().st_size,sha256=h));print(p.name,p.stat().st_size,flush=True)
(cache/'sources.json').write_text(json.dumps(rows,indent=2))
