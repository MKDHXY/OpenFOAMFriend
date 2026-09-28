from pathlib import Path
import urllib.request,json,hashlib,time
root=Path(__file__).resolve().parents[1];cache=root.parent/'installer_cache';cache.mkdir(exist_ok=True)
def get(url,name):
 p=cache/name
 if not p.exists():
  print('Downloading '+name,flush=True)
  with urllib.request.urlopen(url,timeout=120) as r,p.with_suffix(p.suffix+'.part').open('wb') as f:
   while b:=r.read(1024*1024):f.write(b)
  p.with_suffix(p.suffix+'.part').replace(p)
 print(name,p.stat().st_size,flush=True);return p
py=get('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip','python-3.12.10-embed-amd64.zip')
url='https://cloud-images.ubuntu.com/wsl/releases/noble/current/';sha=get(url+'SHA256SUMS','noble_SHA256SUMS');image=get(url+'ubuntu-noble-wsl-amd64-24.04lts.rootfs.tar.gz','ubuntu-noble-wsl-amd64-24.04lts.rootfs.tar.gz')
expected=next(x.split()[0] for x in sha.read_text().splitlines() if image.name in x);assert hashlib.sha256(image.read_bytes()).hexdigest()==expected
with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/microsoft/WSL/releases/latest',headers={'User-Agent':'OpenFoamFriend-Packager'}),timeout=60) as r:release=json.load(r)
a=next(a for a in release['assets'] if a['name'].endswith('.x64.msi'));msi=get(a['browser_download_url'],a['name']);digest=hashlib.sha256(msi.read_bytes()).hexdigest()
if a.get('digest'):assert a['digest']=='sha256:'+digest
(cache/'asset_sources.json').write_text(json.dumps(dict(python=dict(url='https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip',sha256=hashlib.sha256(py.read_bytes()).hexdigest()),ubuntu=dict(url=url+image.name,sha256=expected),wsl=dict(version=release['tag_name'],url=a['browser_download_url'],file=a['name'],sha256=digest)),indent=2))
print('Asset downloads verified',flush=True)
