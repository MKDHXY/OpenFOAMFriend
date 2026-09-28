"""Portable, versioned project format. All geometry and flow values use SI."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import os

@dataclass
class Profile:
    distro: str = 'OpenFoamFriend-14'
    bashrc: str = '/opt/openfoam14/etc/bashrc'
    run_dir: str = '/home/off/OpenFOAM/off14/run'
    max_cores: int = 4
    poll_seconds: int = 10

@dataclass
class Shape:
    kind: str = 'circle'
    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0
    name: str = 'cylinder'

@dataclass
class Region:
    x: float = -2.0
    y: float = -2.0
    width: float = 8.0
    height: float = 4.0
    size: float = 0.1
    direction: str = 'uniform'
    ratio: float = 1.0

@dataclass
class Project:
    name: str = 'Cylinder_Re200'
    dimension: int = 3
    xmin: float = -10.0
    xmax: float = 10.0
    ymin: float = -10.0
    ymax: float = 10.0
    depth: float = 1.0
    shapes: list = field(default_factory=lambda: [asdict(Shape())])
    regions: list = field(default_factory=list)
    curves: list = field(default_factory=list)
    dictionary_overrides: dict = field(default_factory=dict)
    mesh_method: str = 'Structured cylinder O-grid'
    radial: int = 20
    circumferential: int = 64
    spanwise: int = 4
    outer_radius: float = 10.0
    grading: float = 20.0
    cell_size: float = 0.5
    smoothing: int = 10
    nonortho_limit: float = 30.0
    skew_limit: float = 0.5
    reference_length: float = 0.0  # zero: follow single-obstacle geometry
    velocity: float = 1.0
    viscosity: float = 0.005
    end_time: float = 0.05
    delta_t: float = 0.001
    write_interval: float = 0.01
    max_co: float = 0.3
    cores: int = 4
    n_outer_correctors: int = 2
    n_correctors: int = 2
    n_nonorthogonal_correctors: int = 1
    momentum_predictor: bool = True
    turbulence: str = 'laminar'
    turbulence_intensity: float = 0.01
    turbulence_length: float = 0.1
    sa_viscosity_ratio: float = 3.0
    transition_retheta: float = 400.0
    intermittency: float = 1.0
    dynamic_seed: float = 0.01
    manual_mesh: dict = field(default_factory=dict)
    schema: int = 2

    def validate(self):
        import math
        for key,value in asdict(self).items():
            if isinstance(value,(int,float)) and not math.isfinite(value): raise ValueError(key+' must be finite.')
        if self.reference_length<0: raise ValueError('Reference length must be zero (automatic) or positive metres.')
        if self.sa_viscosity_ratio<=0 or self.transition_retheta<=0 or self.dynamic_seed<=0 or not 0<=self.intermittency<=1: raise ValueError('Invalid turbulence seeds: positive SA ratio/ReThetat/dynamic averaging seed, 0<=gammaInt<=1 required.')
        if not self.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in self.name):
            raise ValueError('Case name: use only letters, numbers, underscore and hyphen.')
        if self.dimension not in (2, 3): raise ValueError('Dimension must be 2 or 3.')
        if self.xmax <= self.xmin or self.ymax <= self.ymin: raise ValueError('Domain bounds are inverted.')
        for key in ('depth','velocity','viscosity','end_time','delta_t','write_interval','cell_size','outer_radius','grading'):
            if getattr(self,key) <= 0: raise ValueError(f'{key} must be positive.')
        for key,minimum in [('n_outer_correctors',1),('n_correctors',1),('n_nonorthogonal_correctors',0)]:
            value=getattr(self,key)
            if isinstance(value,bool) or not isinstance(value,int) or value<minimum or value>1024:raise ValueError(key+' must be an integer in range '+str(minimum)+'..1024')
        if not isinstance(self.momentum_predictor,bool):raise ValueError('momentum_predictor must be boolean')
        if not 0 < self.max_co <= 0.3: raise ValueError('Courant limit must be >0 and <=0.3 in this release.')
        if not 0<self.nonortho_limit<=70 or not 0<self.skew_limit<=4: raise ValueError('Quality thresholds: 0<non-orthogonality<=70 degrees, 0<skewness<=4.')
        if self.mesh_method=='Gmsh tetrahedral' and self.dimension==2: raise ValueError('Tetrahedral cells are 3D. For 2D use triangle/prism with one empty layer.')
        if self.cores < 1 or self.radial < 2 or self.spanwise < 1 or self.circumferential < 16 or self.circumferential % 4:
            raise ValueError('Invalid resolution: circumferential count must be a multiple of 4, >=16.')
        from .physics import validate_model,EDITABLE_KEYS
        selected_model=validate_model(self)
        if not 0<self.turbulence_intensity<=1 or self.turbulence_length<=0: raise ValueError('Turbulence intensity is a fraction (0,1]; length scale is positive metres.')
        if self.mesh_method == 'Structured cylinder O-grid':
            if len(self.shapes)!=1 or self.shapes[0]['kind']!='circle': raise ValueError('O-grid requires exactly one circle.')
            s=self.shapes[0]
            if self.outer_radius <= s['width']/2: raise ValueError('Outer radius must exceed cylinder radius.')
            if abs(s['width']-s['height'])>1e-9: raise ValueError('Cylinder must be circular.')
        if self.mesh_method.startswith('Manual topology'):
            from .manual_topology import validate
            validate(self.manual_mesh,'blockMesh' if self.mesh_method.endswith('(blockMesh)') else 'Gmsh')
        for s in self.shapes:
            if s['width']<=0 or s['height']<=0: raise ValueError('Shape dimensions must be positive.')
            if s['kind'] not in ('circle','rectangle','triangle','polygon'): raise ValueError('Unsupported solid kind.')
            if s['kind']=='polygon':
                from .geometry import vertices,validate_polygon
                validate_polygon(vertices(s))
        for r in self.regions:
            if r['size']<=0 or r['ratio']<=0 or r['width']<=0 or r['height']<=0: raise ValueError('Invalid mesh region.')
            if r['direction'] not in ('uniform','x+','x-','y+','y-'): raise ValueError('Invalid grading direction.')
        for c in self.curves:
            if len(c['points'])<2: raise ValueError('A construction curve needs at least two points.')
            if any(len(v)!=2 or not all(__import__('math').isfinite(float(x)) for x in v) for v in c['points']): raise ValueError('Invalid curve coordinates.')
        if 'system/blockMeshDict' in self.dictionary_overrides and not (self.mesh_method.startswith('Structured') or self.mesh_method=='Manual topology (blockMesh)'):
            raise ValueError('Manual blockMeshDict override requires a structured blockMesh method; clear it before Gmsh.')
        for key,value in self.dictionary_overrides.items():
            if key not in EDITABLE_KEYS: raise ValueError('Unsupported dictionary override: '+key)
            if key.startswith('0/') and key[2:] not in ('U','p')+selected_model.fields: raise ValueError('Initial-field override belongs to another model: '+key+'. Review/reset physics overrides before switching models.')
            from .dictionary_editor import validate_foam
            validate_foam(value)

    def save(self,path):
        self.validate(); Path(path).write_text(json.dumps(asdict(self),indent=2),encoding='utf-8')

    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if data.get('schema') not in (1,2): raise ValueError('Unsupported project schema.')
        p=cls(**data); p.validate(); return p

def windows_to_wsl(path):
    p=Path(path).resolve()
    if not p.drive or str(p).startswith('\\\\'): raise ValueError('Use a local drive for generated scripts and meshes.')
    return '/mnt/'+p.drive[0].lower()+'/'+str(p)[3:].replace('\\','/')

def linux_case_path(profile,name): return profile.run_dir.rstrip('/')+'/'+name

def host_path(profile,linux_path):
    if os.name!='nt': return Path(linux_path)
    return Path('\\\\wsl.localhost\\'+profile.distro+'\\'+linux_path.lstrip('/').replace('/','\\'))

def profile_file(): return Path(os.getenv('APPDATA',str(Path.home()))) / 'OpenFoamFriend' / 'profile.json'

def load_profile():
    path=profile_file()
    return Profile(**json.loads(path.read_text())) if path.exists() else Profile()

def save_profile(profile):
    path=profile_file(); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(asdict(profile),indent=2))
