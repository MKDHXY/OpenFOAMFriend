"""OpenSSH + Slurm transport. No passwords, permissive host keys or simulated jobs."""
from dataclasses import dataclass,asdict
from pathlib import Path,PurePosixPath
import subprocess,shlex,re,json,tarfile,time,uuid,os,sys

def client_executable(name):
    """App-local client supports hosts without the optional Windows SSH feature."""
    local=Path(sys.executable).resolve().parent/'tools/openssh'/(name+'.exe')
    return str(local) if local.is_file() else name

@dataclass
class Cluster:
    host: str=''
    user: str=''
    port: int=22
    identity: str=''
    remote_root: str='/scratch/CHANGE_ME/openfoamfriend'
    environment: str='source /opt/openfoam14/etc/bashrc'
    partition: str=''
    account: str=''
    walltime: str='01:00:00'
    cores: int=4
    launcher: str='srun'
    poll_seconds: int=60
    def validate(self):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',self.host) or self.host.startswith('-'): raise ValueError('Enter a host or SSH config alias.')
        if self.user and not re.fullmatch(r'[A-Za-z0-9_.-]+',self.user): raise ValueError('Invalid SSH user.')
        if not 1<=self.port<=65535 or not 1<=self.cores<=4096 or self.poll_seconds<30: raise ValueError('Invalid port/cores; cluster polling must be >=30 s.')
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+',self.remote_root) or '..' in PurePosixPath(self.remote_root).parts: raise ValueError('Use an absolute remote case root without spaces or ..')
        if not re.fullmatch(r'\d{1,3}:\d{2}:\d{2}',self.walltime): raise ValueError('Walltime: HH:MM:SS')
        for value in (self.partition,self.account):
            if value and not re.fullmatch(r'[A-Za-z0-9_.-]+',value): raise ValueError('Invalid partition/account.')
        if self.launcher not in ('srun','mpirun'): raise ValueError('Launcher: srun or mpirun.')
        if not self.environment.strip(): raise ValueError('OpenFOAM environment command required.')
        if self.identity and not Path(self.identity).is_file(): raise ValueError('Private-key path does not exist; key stays local.')

def config_path(): return Path(os.getenv('APPDATA',str(Path.home())))/'OpenFoamFriend'/'cluster.json'
def load_cluster(): return Cluster(**json.loads(config_path().read_text(encoding='utf-8'))) if config_path().exists() else Cluster()
def save_cluster(c): c.validate(); config_path().parent.mkdir(parents=True,exist_ok=True); config_path().write_text(json.dumps(asdict(c),indent=2),encoding='utf-8')
def ssh_args(c):
    c.validate(); args=[client_executable('ssh'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','-p',str(c.port)]
    if c.identity: args+=['-i',c.identity]
    return args+[(c.user+'@' if c.user else '')+c.host]
def remote(c,command,timeout=30):
    result=subprocess.run(ssh_args(c)+['bash -lc '+shlex.quote(command)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode: raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f'SSH exit {result.returncode}')
    return result.stdout.strip()
def probe(c): return remote(c,c.environment+'\nset -e\ncommand -v foamRun\ncommand -v sbatch\ncommand -v squeue\nprintf "OpenFOAM=%s\\n" "$WM_PROJECT_VERSION"\n')
def batch_script(c,case_name,skew=.5,nonortho=30):
    c.validate()
    if not re.fullmatch(r'[A-Za-z0-9_-]+',case_name): raise ValueError('Invalid case name.')
    path=c.remote_root.rstrip('/')+'/'+case_name; lines=['#!/bin/bash',f'#SBATCH --job-name={case_name}',f'#SBATCH --ntasks={c.cores}',f'#SBATCH --time={c.walltime}',f'#SBATCH --chdir={path}', '#SBATCH --output=slurm-%j.out']
    if c.partition: lines.append('#SBATCH --partition='+c.partition)
    if c.account: lines.append('#SBATCH --account='+c.account)
    launch='srun' if c.launcher=='srun' else f'mpirun -np {c.cores}'
    return '\n'.join(lines)+f'\nset -eo pipefail\n{c.environment}\ncd {shlex.quote(path)}\ntrap \'echo FAILED > off.remote.state\' ERR\nexport OMP_NUM_THREADS=1\nif [ -d off_native/dynamicLagrangian ]; then wmake libso off_native/dynamicLagrangian > log.compat_build 2>&1; fi\nif [ ! -d constant/polyMesh ]; then blockMesh > log.mesh 2>&1; fi\ncheckMesh -allGeometry -allTopology -skewThreshold {skew:g} -nonOrthThreshold {nonortho:g} > log.checkMesh 2>&1\ngrep -q "Mesh OK" log.checkMesh\nfoamDictionary system/decomposeParDict -entry numberOfSubdomains -set {c.cores}\ndecomposePar -force > log.decomposePar 2>&1\necho RUNNING > off.remote.state\n{launch} foamRun -solver incompressibleFluid -parallel > log.solver 2>&1\ngrep -q "^End" log.solver\nreconstructPar > log.reconstructPar 2>&1\nfoamToVTK -ascii > log.vtk 2>&1\necho DONE > off.remote.state\n'
def bundle(case,script,destination):
    case=Path(case)
    if not all((case/p).is_dir() for p in ('0','system','constant')): raise ValueError('Select a real OpenFOAM case with 0, system, constant.')
    if not (case/'constant/polyMesh').is_dir() and not (case/'system/blockMeshDict').is_file(): raise ValueError('Remote submission needs an existing polyMesh or blockMeshDict. Generate the Gmsh mesh locally first.')
    with tarfile.open(destination,'w:gz') as archive:
        for folder in ('0','system','constant'):
            for f in (case/folder).rglob('*'):
                if f.is_symlink(): raise ValueError('Symlinks are not supported in upload bundles.')
                if f.is_file() and '.bak_' not in f.name: archive.add(f,arcname=f.relative_to(case).as_posix())
        if (case/'off_native/dynamicLagrangian').is_dir():
            for relative in ('register.C','offDynamicLagrangian.H','offDynamicLagrangian.C','Make/files','Make/options','COPYING','PROVENANCE.json'):
                f=case/'off_native/dynamicLagrangian'/relative
                if f.is_file(): archive.add(f,arcname='off_native/dynamicLagrangian/'+relative)
        import io
        data=script.encode(); info=tarfile.TarInfo('submit.slurm'); info.size=len(data); archive.addfile(info,io.BytesIO(data))
def submit(c,case,script,storage):
    case=Path(case); name=case.name; c.validate(); stamp=uuid.uuid4().hex[:10]; folder=c.remote_root.rstrip('/')+'/'+name
    # Preview is editable, so execute the exact reviewed text, not a regenerated script.
    local=Path(storage)/('upload_'+stamp+'.tar.gz'); local.parent.mkdir(parents=True,exist_ok=True); bundle(case,script,local)
    temporary=c.remote_root.rstrip('/')+'/.upload_'+stamp+'.tar.gz'
    remote(c,'mkdir -p -- '+shlex.quote(c.remote_root)+'\ntest ! -e '+shlex.quote(folder))
    args=[client_executable('scp'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=12','-P',str(c.port)]
    if c.identity: args+=['-i',c.identity]
    result=subprocess.run(args+[str(local),(c.user+'@' if c.user else '')+c.host+':'+temporary],capture_output=True,text=True,timeout=600,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode: raise RuntimeError(result.stderr)
    output=remote(c,'set -e\nmkdir -- '+shlex.quote(folder)+'\ntar -xzf '+shlex.quote(temporary)+' -C '+shlex.quote(folder)+'\ncd '+shlex.quote(folder)+'\nsbatch --parsable submit.slurm',60)
    jobid=output.splitlines()[-1].split(';')[0]
    if not jobid.isdigit(): raise RuntimeError('sbatch did not return a numeric job ID: '+output)
    return {'job_id':jobid,'case':str(case),'remote_case':folder,'cluster':asdict(c),'submitted':time.time(),'script':script,'upload':str(local),'state':'SUBMITTED'}
def query(c,ids):
    if not ids: return ''
    if not all(str(x).isdigit() for x in ids): raise ValueError('Invalid scheduler job IDs.')
    joined=','.join(ids)
    return remote(c,'squeue -h -j '+joined+" -o '%i|%T|%M|%l|%R'\n"+'sacct -n -P -j '+joined+' --format=JobIDRaw,State,Elapsed,ExitCode',30)
def control(c,jobid,action):
    if not str(jobid).isdigit() or action not in ('hold','release','cancel'): raise ValueError('Invalid scheduler action.')
    return remote(c,('scancel '+str(jobid)) if action=='cancel' else 'scontrol '+action+' '+str(jobid))
