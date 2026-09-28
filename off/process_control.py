"""Runs inside Linux: signals only the verified MPI tree for this case."""
import os,sys,signal,json
from pathlib import Path

def control(case,pid,action):
    root=Path('/proc')/str(pid)
    if not root.exists(): raise RuntimeError('Solver process no longer exists.')
    if os.path.realpath(root/'cwd')!=os.path.realpath(case): raise RuntimeError('PID belongs to a different working directory; refusing signal.')
    cmd=(root/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
    if 'foamRun' not in cmd or not any(s in cmd for s in ('mpirun','prterun','prun')): raise RuntimeError('PID is not this OpenFOAM MPI launcher.')
    parents={}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit(): continue
        try: fields=(entry/'stat').read_text().rsplit(')',1)[1].split(); parents[int(entry.name)]=int(fields[1])
        except (FileNotFoundError,PermissionError,IndexError): pass
    descendants=[pid]
    for p in descendants:
        descendants.extend(k for k,v in parents.items() if v==p and k not in descendants)
    sig={'STOP':signal.SIGSTOP,'CONT':signal.SIGCONT,'TERM':signal.SIGTERM}[action]
    order=descendants if action=='STOP' else descendants[::-1]
    for p in order:
        try: os.kill(p,sig)
        except ProcessLookupError: pass
    return {'signal':action,'verified_case':case,'pids':descendants}

if __name__=='__main__': print(json.dumps(control(sys.argv[1],int(sys.argv[2]),sys.argv[3])))
