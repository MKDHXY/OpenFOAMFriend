"""Durable WSL jobs, CPU budget scheduling, real OpenFOAM case dictionaries."""
from pathlib import Path
from dataclasses import asdict
import json, re, shlex, subprocess, time, uuid, sqlite3, os
from .models import Project, Profile, host_path, linux_case_path, windows_to_wsl
from .mesh import header, cylinder_dict, build_gmsh, partitioned_box_dict
from .physics import native_build_command
from .manual_topology import block_dict as manual_dict

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'data'; DATA.mkdir(exist_ok=True)

def wsl(profile,command,timeout=30):
    return subprocess.run(['wsl','-d',profile.distro,'--','bash','-lc',command],capture_output=True,text=True,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def probe(profile):
    r=wsl(profile,'source '+shlex.quote(profile.bashrc)+' >/dev/null 2>&1; command -v foamRun; command -v blockMesh; command -v gmshToFoam; nproc; printenv WM_PROJECT_VERSION')
    if r.returncode or 'foamRun' not in r.stdout: raise RuntimeError(r.stderr or r.stdout or 'OpenFOAM not found')
    return r.stdout.strip()

def write_case(p,profile,preview_root=None):
    p.validate()
    from .reynolds import reference
    reference_l=reference(p)[0]  # reject ambiguous scale before creating any case files
    path=Path(preview_root) if preview_root else host_path(profile,linux_case_path(profile,p.name))
    if (path/'constant'/'polyMesh').exists() or (path/'off.state').exists(): raise FileExistsError('Existing case is protected; choose a new case name or import it.')
    for d in ('0','system','constant'): (path/d).mkdir(parents=True,exist_ok=True)
    def put(d,name,text): (path/d/name).write_text(header(name,'volVectorField' if name=='U' else 'volScalarField' if name=='p' else 'dictionary')+text,encoding='ascii')
    constraint='empty' if p.dimension==2 else 'symmetryPlane'
    put('0','U',f'dimensions [0 1 -1 0 0 0 0];\ninternalField uniform ({p.velocity} 0 0);\nboundaryField\n{{\n inlet {{ type fixedValue; value uniform ({p.velocity} 0 0); }}\n outlet {{ type zeroGradient; }}\n farfield {{ type fixedValue; value uniform ({p.velocity} 0 0); }}\n cylinder {{ type noSlip; }}\n front {{ type {constraint}; }} back {{ type {constraint}; }}\n}}\n')
    put('0','p',f'dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{{ inlet {{ type zeroGradient; }} outlet {{ type fixedValue; value uniform 0; }} farfield {{ type zeroGradient; }} cylinder {{ type zeroGradient; }} front {{ type {constraint}; }} back {{ type {constraint}; }} }}\n')
    put('constant','physicalProperties',f'viscosityModel constant;\nnu [0 2 -1 0 0 0 0] {p.viscosity};\n')
    put('constant','momentumTransport','simulationType laminar;\n')
    put('system','fvSchemes','ddtSchemes { default Euler; }\ngradSchemes { default Gauss linear; }\ndivSchemes { default none; div(phi,U) Gauss linearUpwind grad(U); div((nuEff*dev2(T(grad(U))))) Gauss linear; }\nlaplacianSchemes { default Gauss linear corrected; }\ninterpolationSchemes { default linear; }\nsnGradSchemes { default corrected; }\nwallDist { method meshWave; }\n')
    put('system','fvSolution','solvers\n{ p { solver GAMG; tolerance 1e-8; relTol 0.01; smoother DICGaussSeidel; } pFinal { $p; relTol 0; } U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-9; relTol 0.1; } UFinal { $U; relTol 0; } }\nPIMPLE { nOuterCorrectors '+str(p.n_outer_correctors)+'; nCorrectors '+str(p.n_correctors)+'; nNonOrthogonalCorrectors '+str(p.n_nonorthogonal_correctors)+'; momentumPredictor '+('yes' if p.momentum_predictor else 'no')+'; }\nrelaxationFactors { equations { ".*" 1; } }\n')
    from .physics import write_model_fields,native_library_name,native_build_command
    write_model_fields(p,path)
    native_libs=''
    if p.turbulence=='dynamicLagrangian':
        import shutil
        shutil.copytree(BASE/'native/dynamicLagrangian',path/'off_native/dynamicLagrangian')
        makefile=path/'off_native/dynamicLagrangian/Make/files'
        makefile.write_text('register.C\n\nLIB = $(FOAM_USER_LIBBIN)/'+native_library_name().removesuffix('.so')+'\n',encoding='utf-8',newline='\n')
        native_libs='libs ("'+native_library_name()+'");\n'

    diameter=reference_l if p.mesh_method.startswith('Manual topology') else p.shapes[0]['width'] if p.shapes else 1
    put('system','controlDict',native_libs+f'application foamRun; solver incompressibleFluid;\nstartFrom startTime; startTime 0; stopAt endTime; endTime {p.end_time};\ndeltaT {p.delta_t}; adjustTimeStep yes; maxCo {p.max_co}; maxDeltaT {p.delta_t};\nwriteControl adjustableRunTime; writeInterval {p.write_interval}; purgeWrite 0; writeFormat ascii; writePrecision 10; writeCompression off; timeFormat general; timePrecision 10; runTimeModifiable yes;\nfunctions\n{{ forces {{ type forceCoeffs; libs ("libforces.so"); patches (cylinder); rho rhoInf; rhoInf 1; CofR (0 0 0); liftDir (0 1 0); dragDir (1 0 0); pitchAxis (0 0 1); magUInf {p.velocity}; lRef {reference_l}; Aref {diameter*p.depth}; writeControl timeStep; writeInterval 1; }} }}\n')
    if not p.shapes or (p.mesh_method.startswith('Manual topology') and not any(e['patch']=='cylinder' for e in p.manual_mesh.get('edges',[]))):
        f=path/'system'/'controlDict'; s=f.read_text(); s=s[:s.index('functions\n')]; f.write_text(s+'functions {};\n')
    put('system','decomposeParDict',f'numberOfSubdomains {p.cores}; method scotch;\n')
    if p.mesh_method.startswith('Structured') or p.mesh_method=='Manual topology (blockMesh)':
        (path/'system/blockMeshDict').write_text(manual_dict(p) if p.mesh_method=='Manual topology (blockMesh)' else cylinder_dict(p) if p.mesh_method=='Structured cylinder O-grid' else partitioned_box_dict(p),encoding='utf-8')
    if p.mesh_method.startswith('Manual topology'):
        (path/'manual_topology.json').write_text(json.dumps(p.manual_mesh,indent=2))
        (path/'manual_topology_source.py').write_text((BASE/'off/manual_topology.py').read_text(encoding='utf-8'),encoding='utf-8')
    (path/'mesh_generator_source.py').write_text((BASE/'off/mesh.py').read_text(encoding='utf-8'),encoding='utf-8')
    (path/'mesh_backend.json').write_text(json.dumps({'backend':'blockMesh' if p.mesh_method.startswith('Structured') or p.mesh_method=='Manual topology (blockMesh)' else 'Gmsh → gmshToFoam','method':p.mesh_method,'source_snapshot':'mesh_generator_source.py','actual_mesh':'constant/polyMesh (only after mesh generation)','note':'Gmsh BREP is CAD geometry; MSH is the generated mesh. Draft dictionaries alone are not a solved case.'},indent=2),encoding='utf-8')
    for key,content in p.dictionary_overrides.items():
        target=path/key
        if not target.exists(): raise ValueError('Dictionary is not present for this physics model: '+key)
        target.write_text(content,encoding='utf-8')
    (path/(p.name+'.foam')).touch()
    from .dictionary_editor import format_foam
    for directory in ('0','system','constant'):
        for file in (path/directory).iterdir():
            if file.is_file(): file.write_text(format_foam(file.read_text(encoding='utf-8')),encoding='utf-8')
    (path/'off_project.json').write_text(json.dumps(asdict(p),indent=2))
    return path

def prepare_mesh(p,profile,case):
    if p.mesh_method in ('Structured cylinder O-grid','Structured partitioned box','Manual topology (blockMesh)'):
        from .dictionary_editor import format_foam
        (case/'system'/'blockMeshDict').write_text(format_foam(p.dictionary_overrides.get('system/blockMeshDict') or (manual_dict(p) if p.mesh_method=='Manual topology (blockMesh)' else cylinder_dict(p) if p.mesh_method=='Structured cylinder O-grid' else partitioned_box_dict(p))))
        return 'blockMesh > log.mesh 2>&1'
    import shutil
    local=DATA/(p.name+'.msh'); build_gmsh(p,local)
    shutil.copy2(local,case/'geometry.msh')
    suffix='.geo_unrolled' if p.mesh_method=='Manual topology (Gmsh)' else '.brep'
    shutil.copy2(local.with_suffix(suffix),case/('geometry'+suffix))
    return 'gmshToFoam geometry.msh > log.mesh 2>&1'

def failure_signals(log):
    # sigFpe startup announces exception trapping; it is not a solver failure.
    lines=[line for line in log.splitlines() if not (re.match(r'\s*sigFpe\s*:',line) and 'trapping' in line.lower())]
    return re.findall(r'FOAM FATAL[^\n]*|Floating point exception[^\n]*|\bnan\b|MPI_ABORT', '\n'.join(lines),flags=re.I)

def parse_log(path,end_time):
    if not path.exists(): return {}
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-120000)); text=f.read().decode(errors='replace')
    return parse_log_text(text,end_time)
def parse_log_text(text,end_time):
    times=re.findall(r'^Time =\s*([0-9.eE+-]+)',text,re.M)
    co=re.findall(r'Courant Number mean:\s*\S+\s+max:\s*([\d.eE+-]+)',text)
    residuals=re.findall(r'Solving for (\w+), Initial residual = ([\d.eE+-]+), Final residual = ([\d.eE+-]+)',text)
    failures=failure_signals(text)
    return {'time':float(times[-1]) if times else 0,'co':float(co[-1]) if co else None,'tail_max_co':max(map(float,co)) if co else 0,'progress':min(100,100*float(times[-1])/end_time) if times else 0,'residuals':residuals[-6:],'failure':failures[-1] if failures else None}

def quality(case):
    path=case/'log.checkMesh'
    if not path.exists(): return {}
    text=path.read_text(errors='replace'); vals=quality_text(text,path)
    vals['sets']=[]
    for folder in (case/'postProcessing'/'checkMesh',case/'constant'/'polyMesh'/'sets'):
        if folder.exists():
            for pattern in ('*.vtk','*/*.vtk'): vals['sets'].extend(str(x) for x in folder.glob(pattern))
    return vals
def quality_text(text,path):
    vals={}
    patterns={'cells':r'^\s*cells:\s*(\d+)','aspect_ratio':r'Max aspect ratio =\s*([\d.eE+-]+)','non_orthogonality':r'Mesh non-orthogonality Max:\s*([\d.eE+-]+)','skewness':r'Max skewness =\s*([\d.eE+-]+)'}
    for key,pat in patterns.items():
        m=re.search(pat,text,re.M)
        if m: vals[key]=float(m[1])
    vals['passed']='Mesh OK' in text; vals['log']=str(path)
    vals['sets']=[]
    return vals

class JobStore:
    def __init__(self,db=DATA/'jobs.sqlite'):
        self.db=db
        with sqlite3.connect(db) as c:
            c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS unique_case ON jobs(json_extract(payload,'$.name'))")
    def save(self,j):
        with sqlite3.connect(self.db) as c: c.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)',(j['id'],json.dumps(j)))
    def all(self):
        with sqlite3.connect(self.db) as c: return sorted([json.loads(r[0]) for r in c.execute('SELECT payload FROM jobs ORDER BY rowid')],key=lambda j:j.get('priority',j['created']))
    def claim(self,j,budget):
        with sqlite3.connect(self.db,timeout=20) as c:
            c.execute('BEGIN IMMEDIATE')
            jobs=[json.loads(r[0]) for r in c.execute('SELECT payload FROM jobs')]
            current=next(x for x in jobs if x['id']==j['id'])
            used=sum(x['project']['cores'] for x in jobs if x['state'] in ('STARTING','MESHING','CHECKING','RUNNING','PAUSED','EXPORTING'))
            if current['state']!='QUEUED' or used+j['project']['cores']>budget: return False
            j['state']='STARTING'; j['started']=time.time()
            c.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(j),j['id']))
            return True

class Engine:
    def __init__(self,profile,store=None): self.profile=profile; self.store=store or JobStore(); self.last_poll_error=None
    def enqueue(self,p,mesh_only=False):
        p.validate()
        if p.cores>self.profile.max_cores: raise ValueError('Requested cores exceed configured CPU budget.')
        if any(j['name']==p.name for j in self.store.all()): raise ValueError('Case already registered; choose a unique name.')
        case=write_case(p,self.profile)
        cmd=prepare_mesh(p,self.profile,case)
        j={'id':uuid.uuid4().hex,'name':p.name,'state':'QUEUED','created':time.time(),'project':asdict(p),'case':str(case),'linux_case':linux_case_path(self.profile,p.name),'mesh_command':cmd,'mesh_only':mesh_only,'profile':asdict(self.profile)}
        self.store.save(j); return j
    def launch(self,j):
        if not self.store.claim(j,self.profile.max_cores): return
        p=Project(**j['project']); c=Path(j['case']); profile=Profile(**j['profile'])
        from .physics import native_build_command
        patch_py="import re,pathlib; f=pathlib.Path('constant/polyMesh/boundary'); s=f.read_text();\nfor name,typ in [('cylinder','wall'),('front','"+('empty' if p.dimension==2 else 'symmetryPlane')+"'),('back','"+('empty' if p.dimension==2 else 'symmetryPlane')+"')]:\n s=re.sub(r'('+name+r'\\s*\\{[^}]*?type\\s+)\\w+',lambda m:m[1]+typ,s)\nf.write_text(s)"
        script='#!/bin/bash\nsource '+shlex.quote(profile.bashrc)+' >/dev/null 2>&1\nset -e\ncd '+shlex.quote(j['linux_case'])+'\ntrap \'echo FAILED > off.state\' ERR\necho MESHING > off.state\n'+native_build_command(p)+j['mesh_command']+'\npython3 -c '+shlex.quote(patch_py)+'\necho CHECKING > off.state\ncheckMesh -allGeometry -allTopology -nonOrthThreshold '+str(p.nonortho_limit)+' -skewThreshold '+str(p.skew_limit)+' -writeSets -writeSurfaces > log.checkMesh 2>&1\ngrep -q "Mesh OK" log.checkMesh\n'
        if not j['mesh_only']:
            script+='decomposePar -force > log.decomposePar 2>&1\necho RUNNING > off.state\ndate +%s > off.start\nsetsid mpirun --oversubscribe -np '+str(p.cores)+' foamRun -solver incompressibleFluid -parallel > log.solver 2>&1 &\npid=$!\necho "$pid" > off.pgid\n(while kill -0 "$pid" 2>/dev/null; do date +%s > off.heartbeat; sleep 10; done) &\nwatcher=$!\nwait "$pid"\nkill "$watcher" 2>/dev/null || true\ngrep -q "^End" log.solver\necho EXPORTING > off.state\nreconstructPar > log.reconstructPar 2>&1\nfoamToVTK -ascii > log.vtk 2>&1\n'
        script+='echo DONE > off.state\ndate +%s > off.end\n'
        file=DATA/(j['id']+'.sh'); file.write_text(script,newline='\n')
        with (c/'log.driver').open('wb') as log:
            proc=subprocess.Popen(['wsl','-d',profile.distro,'--','bash',windows_to_wsl(file)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
        j['state']='STARTING'; j['started']=time.time(); j['driver_pid']=proc.pid
        self.store.save(j)
    def tick(self):
        # One scheduler can mutate the queue at a time, even with GUI+worker.
        lockpath=Path(str(self.store.db)+'.lock'); lockpath.touch(exist_ok=True)
        with lockpath.open('r+b') as lock:
            if lockpath.stat().st_size==0: lock.write(b'0'); lock.flush()
            lock.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt; msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl; fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: return self.store.all()
            try: return self._tick()
            finally:
                lock.seek(0)
                if os.name=='nt': msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                else: fcntl.flock(lock,fcntl.LOCK_UN)
    def _tick(self):
        jobs=self.store.all(); active=0; snapshots={}; groups={}
        for j in jobs:
            if j['state'] not in ('QUEUED','CANCELLED') and (j['state'] not in ('DONE','FAILED') or 'log_tail' not in j): groups.setdefault(j['profile']['distro'],[]).append({'id':j['id'],'case':j['linux_case']})
        for distro,items in groups.items():
            try:
                result=subprocess.run(['wsl','-d',distro,'--','python3',windows_to_wsl(BASE/'off'/'remote_status.py'),json.dumps(items)],capture_output=True,text=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            except subprocess.TimeoutExpired:
                self.last_poll_error='WSL status probe timed out; displayed job states are cached. Polling will retry; no new job is launched until live status returns.'
                return jobs
            if result.returncode: raise RuntimeError('WSL status probe failed: '+result.stderr)
            snapshots.update(json.loads(result.stdout))
        self.last_poll_error=None
        for j in jobs:
            c=Path(j['case']); snapshot=snapshots.get(j['id'])
            if snapshot and snapshot['state']:
                s=snapshot['state']
                if j['state']=='PAUSED' and s=='RUNNING': s='PAUSED'
                j['state']=s
            p=Project(**j['project'])
            if snapshot:
                if snapshot['solver']: j.update(parse_log_text(snapshot['solver'],p.end_time))
                if snapshot['check']:
                    j['quality']=quality_text(snapshot['check'],c/'log.checkMesh'); j['quality']['sets']=[str(host_path(Profile(**j['profile']),path)) for path in snapshot['sets']]
                j['log_tail']='\n'.join(snapshot['solver'].splitlines()[-35:]); j['check_tail']='\n'.join(snapshot['check'].splitlines()[-35:])
                if j['state']=='FAILED' and not j['log_tail']: j['log_tail']=snapshot.get('preparation','')[-16000:]
                if j['state']=='DONE' and snapshot['start'] and snapshot['end']: j['elapsed']=int(snapshot['end'])-int(snapshot['start'])
            j['max_observed_co']=max(j.get('max_observed_co',0),j.get('tail_max_co',0))
            heartbeat=snapshot['heartbeat'] if snapshot else None
            if j['state']=='RUNNING' and heartbeat and time.time()-heartbeat>max(60,3*self.profile.poll_seconds):
                j['state']='STALLED'; j['error']='Solver driver heartbeat lost. Inspect processes; resume saved fields after reboot.'
            if j['state'] in ('STARTING','MESHING','CHECKING','RUNNING','PAUSED','EXPORTING') or (j['state']=='STALLED' and snapshot and snapshot['mpi_live']):
                active+=p.cores
                elapsed=max(0,time.time()-j.get('started',time.time())-j.get('paused_seconds',0))
                j['elapsed']=elapsed; t=j.get('time',0)
                advanced=t-j.get('resumed_from',0)
                j['eta']=elapsed*(p.end_time-t)/advanced if advanced>0 and j['state']=='RUNNING' else None
            self.store.save(j)
        for j in jobs:
            if j['state']=='QUEUED' and active+j['project']['cores']<=self.profile.max_cores:
                self.launch(j); active+=j['project']['cores']
        return self.store.all()
    def signal(self,j,action):
        if action not in ('STOP','CONT','TERM'): raise ValueError('Unsupported signal')
        c=Path(j['case']); pidfile=c/'off.pgid'
        if not pidfile.exists(): raise RuntimeError('No active solver group; wait until RUNNING.')
        pgid=int(pidfile.read_text()); profile=Profile(**j['profile'])
        r=subprocess.run(['wsl','-d',profile.distro,'--','python3',windows_to_wsl(BASE/'off'/'process_control.py'),j['linux_case'],str(pgid),action],capture_output=True,text=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if r.returncode: raise RuntimeError(r.stderr)
        if action=='STOP': j['state']='PAUSED'; j['paused_at']=time.time()
        elif action=='CONT': j['state']='RUNNING'; j['paused_seconds']=j.get('paused_seconds',0)+time.time()-j.pop('paused_at',time.time())
        else: j['state']='CANCELLED'; (c/'off.state').write_text('CANCELLED')
        self.store.save(j)
        return r.stdout.strip()
    def cancel(self,j):
        if j['state']=='QUEUED': j['state']='CANCELLED'; self.store.save(j)
        elif j['state'] in ('RUNNING','PAUSED'): self.signal(j,'CONT') if j['state']=='PAUSED' else None; self.signal(j,'TERM')
        else: raise ValueError('Cancellation is available for QUEUED, RUNNING and PAUSED jobs.')
    def reorder(self,j,direction):
        waiting=[x for x in self.store.all() if x['state']=='QUEUED']
        index=next((i for i,x in enumerate(waiting) if x['id']==j['id']),-1); other=index+direction
        if index<0 or not 0<=other<len(waiting): return
        a,b=waiting[index],waiting[other]; a['priority'],b['priority']=b.get('priority',b['created']),a.get('priority',a['created']); self.store.save(a); self.store.save(b)
    def resume_saved(self,j):
        if j['state'] not in ('FAILED','STALLED'): raise ValueError('Checkpoint recovery is only for failed or stalled cases.')
        c=Path(j['case']); p=Project(**j['project']); profile=Profile(**j['profile'])
        active=sum(x['project']['cores'] for x in self.store.all() if x['id']!=j['id'] and x['state'] in ('STARTING','MESHING','CHECKING','RUNNING','PAUSED','EXPORTING'))
        if active+p.cores>self.profile.max_cores: raise ValueError('Wait for the CPU budget before checkpoint recovery.')
        if (c/'off.pgid').exists():
            pgid=int((c/'off.pgid').read_text())
            if wsl(profile,f'kill -0 {pgid} 2>/dev/null').returncode==0: raise ValueError('The old solver process is still alive; inspect it before recovery.')
        times=[]
        for rank in range(p.cores):
            saved=[]
            for d in (c/f'processor{rank}').iterdir():
                try: t=float(d.name)
                except ValueError: continue
                if (d/'U').exists() and (d/'p').exists(): saved.append(t)
            if not saved: raise ValueError('No complete U,p checkpoint in every rank.')
            times.append(max(saved))
        if max(times)-min(times)>1e-10: raise ValueError('Latest processor checkpoints do not match; inspect before recovery.')
        if times[0]>=p.end_time: raise ValueError('Solver is already at end time; only export/reconstruction needs recovery.')
        control=c/'system'/'controlDict'; control.write_text(re.sub(r'startFrom\s+\w+;', 'startFrom latestTime;',control.read_text()))
        if (c/'log.solver').exists(): (c/'log.solver').rename(c/f'log.solver.before_resume_{int(time.time())}')
        script='#!/bin/bash\nsource '+shlex.quote(profile.bashrc)+' >/dev/null 2>&1\nset -e\ncd '+shlex.quote(j['linux_case'])+'\ntrap \'echo FAILED > off.state\' ERR\necho RUNNING > off.state\n'+native_build_command(p)+'setsid mpirun --oversubscribe -np '+str(p.cores)+' foamRun -solver incompressibleFluid -parallel > log.solver 2>&1 &\npid=$!; echo "$pid" > off.pgid\n(while kill -0 "$pid" 2>/dev/null; do date +%s > off.heartbeat; sleep 10; done) &\nwatcher=$!; wait "$pid"; kill "$watcher" 2>/dev/null || true\necho EXPORTING > off.state\nreconstructPar > log.reconstructPar 2>&1\nfoamToVTK -ascii > log.vtk 2>&1\necho DONE > off.state\ndate +%s > off.end\n'
        f=DATA/(j['id']+'_resume.sh'); f.write_text(script,newline='\n')
        with (c/'log.driver').open('ab') as log: proc=subprocess.Popen(['wsl','-d',profile.distro,'--','bash',windows_to_wsl(f)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        j['state']='STARTING'; j['resumed_from']=times[0]; j['started']=time.time(); j['driver_pid']=proc.pid; self.store.save(j)
