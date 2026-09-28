"""Foundation 14 incompressible Newtonian model catalogue and field contract.
Source: /opt/openfoam14/src/MomentumTransportModels/incompressible/incompressibleMomentumTransportModels.C
Guide: https://doc.cfd.direct/openfoam/user-guide/turbulence
Each selected model gets its actual transported fields; transient RAS is URANS.
"""
from dataclasses import dataclass
@dataclass(frozen=True)
class Model:
    name:str
    family:str
    fields:tuple
    description:str

MODELS={m.name:m for m in [
    Model('laminar','Laminar',(),'No eddy-viscosity model. DNS is a resolution claim, not a separate switch.'),
    Model('SpalartAllmaras','RAS',('nuTilda','nut'),'One-equation eddy viscosity; commonly used for aerodynamic boundary layers.'),
    *[Model(n,'RAS',('k','epsilon','nut'),d) for n,d in [
        ('kEpsilon','Standard two-equation k–epsilon; wall functions.'),
        ('RNGkEpsilon','RNG k–epsilon; strain-sensitive correction.'),
        ('realizableKE','Realizable k–epsilon; variable eddy-viscosity coefficient.'),
        ('LaunderSharmaKE','Low-Re k–epsilon; wall-resolved near-wall mesh required.')]],
    *[Model(n,'RAS',('k','omega','nut'),d) for n,d in [
        ('kOmega','Standard k–omega; wall-resolved option.'),('kOmega2006','Revised 2006 k–omega formulation.'),
        ('kOmegaSST','SST k–omega; adverse-pressure-gradient/separation applications.'),
        ('kOmegaSSTSAS','Scale-adaptive SST; needs temporal and spatial resolution for resolved structures.')]],
    Model('kOmegaSSTLM','RAS',('k','omega','nut','ReThetat','gammaInt'),'SST transition model. Inlet transition seeds require problem-specific calibration.'),
    Model('v2f','RAS',('k','epsilon','v2','f','nut'),'Four-equation elliptic-relaxation model; wall-resolved mesh.'),
    *[Model(n,'RAS',('R','epsilon','nut'),'Reynolds-stress transport model; tensor stress and epsilon.') for n in ('LRR','SSG')],
    *[Model(n,'LES',('nut',),'Algebraic subgrid model; genuine 3D and adequate resolved turbulence required.') for n in ('Smagorinsky','WALE')],
    *[Model(n,'LES',('k','nut'),'Subgrid kinetic-energy transport; genuine 3D and appropriate filter width.') for n in ('kEqn','dynamicKEqn')],
    Model('dynamicLagrangian','LES',('flm','fmm','nut'),'Lagrangian dynamic SGS; dimension-correct isolated Foundation 14 compatibility module (wmake required); positive U^4 averaging seeds.'),
    Model('DeardorffDiffStress','LES',('R','nut'),'Subgrid stress transport; tensor stress rather than only eddy viscosity.'),
    *[Model(n,'Hybrid',('nuTilda','nut'),'Hybrid RANS/LES. Mesh-dependent switching must be assessed; no automatic accuracy guarantee.') for n in ('SpalartAllmarasDES','SpalartAllmarasDDES','SpalartAllmarasIDDES')],
    Model('kOmegaSSTDES','Hybrid',('k','omega','nut'),'SST-based detached-eddy simulation; 3D wake resolution is essential.')
]}
FIELDS=tuple(sorted({f for m in MODELS.values() for f in m.fields}))
EDITABLE_KEYS=tuple('0/'+n for n in ('U','p')+FIELDS)+('system/blockMeshDict','system/fvSchemes','system/fvSolution','constant/physicalProperties','constant/momentumTransport')
def validate_model(p):
    if p.turbulence not in MODELS: raise ValueError('Unknown Foundation 14 model: '+p.turbulence)
    model=MODELS[p.turbulence]
    if model.family in ('LES','Hybrid') and (p.dimension!=3 or p.spanwise<2):
        raise ValueError('LES/DES requires a 3D volume with at least two spanwise cells. Software acceptance is not resolution validation.')
    return model

def write_model_fields(p,path):
    """Generate complete field/dictionary contracts; model defaults are not calibration."""
    from .mesh import header
    model=validate_model(p)
    if model.family=='Laminar': return
    runtime_name='offDynamicLagrangian' if p.turbulence=='dynamicLagrangian' else model.name
    simulation='RAS' if model.family=='RAS' else 'LES'
    coefficients=' delta cubeRootVol; ' if p.turbulence=='kOmegaSSTSAS' else ''
    if simulation=='LES':
        delta='IDDESDelta' if p.turbulence=='SpalartAllmarasIDDES' else 'maxDeltaxyz' if model.family=='Hybrid' else 'cubeRootVol'
        coefficients=f' delta {delta}; '
        if p.turbulence in ('dynamicLagrangian','dynamicKEqn'): coefficients+=f'{runtime_name}Coeffs {{ filter simple; }} '
    (path/'constant/momentumTransport').write_text(header('momentumTransport')+f'simulationType {simulation};\n{simulation} {{ model {runtime_name}; turbulence on; printCoeffs on;{coefficients} }}\n')
    k=1.5*(p.velocity*p.turbulence_intensity)**2
    omega=k**.5/(.09**.25*p.turbulence_length)
    epsilon=.09**.75*k**1.5/p.turbulence_length
    values={'k':(k,'[0 2 -2 0 0 0 0]'),'omega':(omega,'[0 0 -1 0 0 0 0]'),'epsilon':(epsilon,'[0 2 -3 0 0 0 0]'),
        'nut':(k/omega,'[0 2 -1 0 0 0 0]'),'nuTilda':(p.sa_viscosity_ratio*p.viscosity,'[0 2 -1 0 0 0 0]'),
        'v2':(2*k/3,'[0 2 -2 0 0 0 0]'),'f':(0.,'[0 0 -1 0 0 0 0]'),
        'R':('('+ ' '.join(format(v,'.16g') for v in (2*k/3,0,0,2*k/3,0,2*k/3))+')','[0 2 -2 0 0 0 0]'),
        'ReThetat':(p.transition_retheta,'[0 0 0 0 0 0 0]'),'gammaInt':(p.intermittency,'[0 0 0 0 0 0 0]'),
        'flm':(p.dynamic_seed,'[0 4 -4 0 0 0 0]'),'fmm':(p.dynamic_seed,'[0 4 -4 0 0 0 0]')}
    low_re=p.turbulence in ('LaunderSharmaKE','v2f','SpalartAllmaras') or model.family in ('LES','Hybrid')
    constraint='empty' if p.dimension==2 else 'symmetryPlane'
    for name in model.fields:
        value,dimensions=values[name]; val=format(value,'.16g') if isinstance(value,(int,float)) else value
        wall={'k':'kqRWallFunction','epsilon':'epsilonWallFunction','omega':'omegaWallFunction','nut':'nutkWallFunction','v2':'v2WallFunction','f':'fWallFunction','R':'kqRWallFunction'}.get(name,'zeroGradient')
        wallval=val
        if name=='nuTilda': wall='fixedValue'; wallval='0'
        if low_re and name=='nut': wall='nutLowReWallFunction'; wallval='0'
        if p.turbulence=='LaunderSharmaKE' and name in ('k','epsilon'):
            wall='fixedValue'; wallval='0' if name=='k' else format(max(epsilon*1e-8,1e-20),'.16g')  # explicit positive wall regularisation avoids 0/0 in fMu
        if p.turbulence=='v2f' and name in ('k','v2','f'): wall='fixedValue'; wallval='0'
        if model.family in ('LES','Hybrid') and name in ('k','R'):
            wall='fixedValue'; wallval='(0 0 0 0 0 0)' if name=='R' else '0'
        if name in ('ReThetat','gammaInt','flm','fmm'): wall='zeroGradient'
        opening='calculated' if name=='nut' else 'fixedValue'
        outlet='calculated' if name=='nut' else 'zeroGradient'
        body=f'dimensions {dimensions};\ninternalField uniform {val};\nboundaryField {{ inlet {{ type {opening}; value uniform {val}; }} outlet {{ type {outlet}; value uniform {val}; }} farfield {{ type {opening}; value uniform {val}; }} cylinder {{ type {wall}; value uniform {wallval}; }} front {{ type {constraint}; }} back {{ type {constraint}; }} }}\n'
        (path/'0'/name).write_text(header(name,'volSymmTensorField' if name=='R' else 'volScalarField')+body)
    transported=[n for n in model.fields if n not in ('nut',)]
    file=path/'system/fvSchemes'; s=file.read_text(); divs=' '.join(f'div(phi,{name}) Gauss upwind;' for name in transported)
    s=s.replace('div(phi,U) Gauss linearUpwind grad(U);','div(phi,U) Gauss linearUpwind grad(U); '+divs)
    file.write_text(s)
    file=path/'system/fvSolution'; s=file.read_text()
    entries=' '.join(f'{name} {{ solver smoothSolver; smoother symGaussSeidel; tolerance 1e-8; relTol 0.1; }} {name}Final {{ ${name}; relTol 0; }}' for name in transported)
    file.write_text(s.replace('solvers\n{','solvers\n{ '+entries+' '))


def native_library_name():
    from pathlib import Path
    return 'liboffDynamicLagrangian_'+Path(__file__).resolve().parents[1].name+'.so'

def native_build_command(p):
    if p.turbulence!='dynamicLagrangian': return ''
    library=native_library_name()
    return f'if [ ! -s "$FOAM_USER_LIBBIN/{library}" ]; then wmake libso off_native/dynamicLagrangian > log.compat_build 2>&1; fi\n'

MODEL_DESCRIPTIONS_ZH={
'laminar':'无涡黏度模型。DNS 是网格与时间分辨率的验证结论，不是单独开关。',
'SpalartAllmaras':'SA 单方程涡黏度模型，常用于空气动力边界层。',
'kEpsilon':'标准 k–epsilon 双方程模型，采用壁面函数。',
'RNGkEpsilon':'RNG k–epsilon，包含应变相关修正。',
'realizableKE':'可实现 k–epsilon，使用可变涡黏度系数。',
'LaunderSharmaKE':'低雷诺数 k–epsilon，要求壁面解析网格；epsilon 壁面使用显式正值数值正则化，需核对。',
'kOmega':'标准 k–omega 双方程模型。',
'kOmega2006':'2006 年修订的 k–omega 模型。',
'kOmegaSST':'SST k–omega，常用于逆压梯度和分离流动。',
'kOmegaSSTSAS':'SST 尺度自适应模型；须有足够时空分辨率以解析流动结构。',
'kOmegaSSTLM':'SST 转捩模型；入口 ReThetat 与间歇因子须按工况设定。',
'v2f':'四方程椭圆松弛模型，要求壁面解析网格。',
'LRR':'LRR 雷诺应力输运模型，求解对称应力张量 R 与 epsilon。',
'SSG':'SSG 雷诺应力输运模型，求解对称应力张量 R 与 epsilon。',
'Smagorinsky':'代数亚格子模型，须三维并具有足够可解析湍流分辨率。',
'WALE':'壁面自适应局部涡黏度亚格子模型，须三维与足够分辨率。',
'kEqn':'亚格子动能输运模型，须三维并选择适当滤波尺度。',
'dynamicKEqn':'动态亚格子动能输运模型，使用 simple 测试滤波。',
'dynamicLagrangian':'拉格朗日动态亚格子模型；本版使用独立量纲修正模块，需 wmake。flm/fmm 初值量纲为速度四次方。',
'DeardorffDiffStress':'亚格子应力输运，求解对称应力张量 R。',
'kOmegaSSTDES':'SST 混合 RANS/LES；必须评估三维尾流网格与模型切换。',
'SpalartAllmarasDES':'SA 分离涡模拟，混合 RANS/LES；模型切换与网格相关。',
'SpalartAllmarasDDES':'SA 延迟分离涡模拟；必须验证屏蔽及解析湍流分辨率。',
'SpalartAllmarasIDDES':'SA 改进延迟分离涡模拟，使用 IDDESDelta；必须评估三维网格与壁面处理。'
}
