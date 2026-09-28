"""Offline installer primitives. Lite has no Linux/system installation code path."""
from pathlib import Path
import os,sys,json,shutil,hashlib,subprocess,re,platform,time,shlex

def run(args,timeout=60):
    args=list(args)
    if str(args[0]).lower() in ('powershell.exe','wsl.exe'):
        system=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'
        args[0]=system/'WindowsPowerShell/v1.0/powershell.exe' if str(args[0]).lower()=='powershell.exe' else system/'wsl.exe'
    p=subprocess.run([str(x) for x in args],capture_output=True,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def decode(b):return b.decode('utf-16-le' if b'\x00' in b[:100] else 'utf-8',errors='replace').replace('\x00','').strip()
    if p.returncode:raise RuntimeError(f'Exit {p.returncode}: '+decode(p.stderr or p.stdout))
    return decode(p.stdout)

def environment(distro=None,bashrc='/opt/openfoam14/etc/bashrc'):
    report=dict(windows=platform.platform(),architecture=platform.machine(),python=sys.executable,wsl_present=bool(shutil.which('wsl.exe') or (Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/wsl.exe').exists()),distributions=[],ready=False,errors=[])
    if not report['wsl_present']:report['errors'].append('WSL missing / 未安装 WSL');return report
    try:
        report['distributions']=[s.strip() for s in run(['wsl.exe','--list','--quiet'],30).splitlines() if s.strip()]
        if not report['distributions']:report['errors'].append('No WSL distribution / 未安装 Linux 发行版');return report
        if distro and distro not in report['distributions']:report['errors'].append('Distribution not found / 发行版不存在: '+distro);return report
        candidates=[distro] if distro else report['distributions']
        for name in candidates:
            try:
                out=run(['wsl.exe','-d',name,'--','bash','-lc',f'source {shlex.quote(bashrc)} >/dev/null 2>&1 && command -v foamRun && command -v blockMesh && command -v gmshToFoam && command -v mpirun && printenv WM_PROJECT_VERSION && id -un && printenv HOME'],40)
                lines=out.splitlines()
                if lines[-3]!='14':raise RuntimeError('OpenFOAM Foundation 14 required / 需要 Foundation 14，检测到 '+lines[-3])
                report.update(ready=True,distro=name,bashrc=bashrc,user=lines[-2],home=lines[-1],probe=out,foam_version=lines[-3]);return report
            except Exception as e:report['errors'].append(name+': '+str(e))
    except Exception as e:report['errors'].append(str(e))
    return report

def verify_bundle(bundle,progress=lambda s:None):
    bundle=Path(bundle);m=json.loads((bundle/'bundle_manifest.json').read_text(encoding='utf-8'))
    for i,(relative,expected) in enumerate(m['sha256'].items()):
        p=(bundle/relative).resolve()
        if not p.is_relative_to(bundle.resolve()) or not p.is_file():raise RuntimeError('Missing/unsafe payload: '+relative)
        with p.open('rb') as stream:h=hashlib.file_digest(stream,'sha256').hexdigest()
        if h!=expected:raise RuntimeError('Corrupt payload: '+relative)
        if i%300==0:progress(f'Verify / 校验 {i+1}/{len(m["sha256"])}')
    return m

def shortcuts(target,release):
    def quote(v):return "'"+str(v).replace("'","''")+"'"
    script=f"$s=New-Object -ComObject WScript.Shell; foreach($d in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('Programs'))){{$l=$s.CreateShortcut((Join-Path $d 'Open Foam Friend.lnk'));$l.TargetPath={quote(target/'Open Foam Friend.cmd')};$l.WorkingDirectory={quote(target)};$l.IconLocation={quote(target/release/'assets/icon.ico')};$l.Save()}}"
    run(['powershell.exe','-NoProfile','-Command',script])

def install(bundle,target,distro='OpenFoamFriend-14',progress=lambda s:None,make_shortcuts=True,configure_profile=True):
    bundle=Path(bundle).resolve();target=Path(target).expanduser().resolve();mode=json.loads((bundle/'bundle.json').read_text())['mode']
    if mode not in ('full','lite'):raise ValueError('Unknown package mode')
    if platform.machine().lower() not in ('amd64','x86_64'):raise RuntimeError('Windows x64 only / 本包仅适用于 Windows x64')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',distro):raise ValueError('Invalid WSL name / 发行版名只能用英文数字下划线横线')
    m=verify_bundle(bundle,progress);release=m['release']
    if target==bundle or bundle.is_relative_to(target):raise ValueError('Installation must be separate from the extracted installer / 安装目录须与解压目录分开')
    if target.exists() and any(target.iterdir()) and not (target/'off_install.json').exists():raise FileExistsError('Nonempty unmanaged folder protected / 已保护非空的非本软件目录')
    target.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(target.parent).free<10*1024**3:raise RuntimeError('At least 10 GB free space required / 至少需要 10 GB 可用空间')
    if mode=='full' and sys.getwindowsversion().build<19041:raise RuntimeError('Windows 10 build 19041 or Windows 11 required / 需要 Windows 10 19041 或 Windows 11')
    target.mkdir(exist_ok=True)
    (target/'off_install.json').write_text(json.dumps(dict(mode=mode,release=release,distro=distro,stage='preparing'),indent=2))
    if mode=='full':
        progress('Checking WSL / 检查 WSL')
        names=run(['wsl.exe','--list','--quiet'],30).splitlines()
        if distro in names:
            marker=run(['wsl.exe','-d',distro,'-u','root','--','cat','/etc/openfoamfriend/build-info'],30)
            if 'Open Foam Friend clean environment' not in marker:raise RuntimeError('Existing distribution is protected / 已保护同名非本软件发行版')
        else:
            location=target/'wsl'/distro
            if location.exists() and any(location.iterdir()):raise FileExistsError('Existing WSL storage protected / 已保护已有 WSL 存储')
            location.parent.mkdir(parents=True,exist_ok=True);progress('Importing prepared Linux image; may take minutes / 导入已配置 Linux 镜像，可能需数分钟')
            run(['wsl.exe','--import',distro,location,bundle/'payload/openfoam14-ubuntu24.04.tar.gz','--version','2'],600)
        report=environment(distro)
        if not report['ready']:raise RuntimeError(json.dumps(report,ensure_ascii=False,indent=2))
    else:
        # Read-only detection only. Never invokes MSI/DISM, imports a distro, apt, or pip.
        progress('Detect only; Linux is never installed / 仅检测，绝不安装 Linux 环境');report=environment()
    progress('Installing local runtime and application / 安装自带运行环境与软件')
    target.mkdir(exist_ok=True);(target/'off_install.json').write_text(json.dumps(dict(mode=mode,release=release,distro=distro,stage='copying'),indent=2))
    shutil.copytree(bundle/'runtime',target/'runtime',dirs_exist_ok=True)
    shutil.copytree(bundle/'application'/release,target/release,dirs_exist_ok=True)
    (target/'LATEST.txt').write_text(release+'\n',encoding='ascii')
    (target/'Open Foam Friend.cmd').write_text('@echo off\nsetlocal\nset /p off_version=<"%~dp0LATEST.txt"\ncall "%~dp0%off_version%\\launch.cmd"\n',encoding='ascii')
    # No global Python installation, pip downloads, PATH changes or system-runtime dependency.
    run([target/'runtime/python.exe','-X','utf8',target/release/'tools/diagnose.py'],120)
    if configure_profile and report.get('ready'):
        profile=Path(os.environ.get('APPDATA',str(Path.home())))/'OpenFoamFriend/profile.json';profile.parent.mkdir(parents=True,exist_ok=True)
        if profile.exists():shutil.copy2(profile,profile.with_name('profile.before_install_'+time.strftime('%Y%m%d_%H%M%S')+'.json'))
        run_dir='/home/off/OpenFOAM/off14/run' if mode=='full' else report['home']+'/OpenFOAM/'+report['user']+'14/run'
        if mode=='full':run(['wsl.exe','-d',report['distro'],'--','mkdir','-p',run_dir])
        profile.write_text(json.dumps(dict(distro=report['distro'],bashrc=report['bashrc'],run_dir=run_dir,max_cores=min(4,os.cpu_count() or 1),poll_seconds=30),indent=2))
    if make_shortcuts:shortcuts(target,release)
    record=dict(mode=mode,release=release,distro=report.get('distro'),environment=report,installed=True,completed=time.strftime('%Y-%m-%d %H:%M:%S'))
    (target/'off_install.json').write_text(json.dumps(record,indent=2,ensure_ascii=False));return record
