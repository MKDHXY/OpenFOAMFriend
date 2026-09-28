"""Runs inside Linux: collect a batch without Windows UNC hot-file reads."""
import sys,json,os
from pathlib import Path
def read(path,tail=None):
    try:
        with path.open('rb') as f:
            if tail: f.seek(max(0,path.stat().st_size-tail))
            return f.read().decode('utf-8',errors='replace')
    except OSError: return ''
def main():
    result={}
    for item in json.loads(sys.argv[1]):
        c=Path(item['case']); heartbeat=c/'off.heartbeat'; sets=[]
        for folder in (c/'postProcessing'/'checkMesh',c/'constant'/'polyMesh'/'sets'):
            if folder.exists():
                for pattern in ('*.vtk','*/*.vtk'): sets.extend(str(p) for p in folder.glob(pattern))
        live=False
        try:
            pid=int(read(c/'off.pgid').strip()); os.kill(pid,0)
            live=Path(f'/proc/{pid}/cwd').resolve()==c.resolve()
        except (OSError,ValueError): pass
        result[item['id']]={'state':read(c/'off.state').strip(),'solver':read(c/'log.solver',120000),'check':read(c/'log.checkMesh',200000),'start':read(c/'off.start').strip(),'end':read(c/'off.end').strip(),'heartbeat':heartbeat.stat().st_mtime if heartbeat.exists() else None,'sets':sets,'mpi_live':live,'preparation':'\n'.join(read(c/name,8000) for name in ('log.driver','log.compat_build','log.mesh','log.decomposePar','log.reconstructPar','log.vtk'))}
    print(json.dumps(result))
if __name__=='__main__': main()
