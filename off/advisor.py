"""Explainable setup screening, not an automatic physical validation service.

Thresholds below are conservative application heuristics. Cylinder regime notes
are limited to an isolated smooth circular cylinder, not universal Re criteria.
"""
import hashlib,json,math
from dataclasses import asdict
from .reynolds import reference,reynolds
from .physics import MODELS

SOURCES=[
 {'label':'CFD Direct. OpenFOAM v14 User Guide: Turbulence models.','url':'https://doc.cfd.direct/openfoam/user-guide/turbulence'},
 {'label':'Greenshields, C., & Weller, H. Notes on CFD: Turbulence near walls.','url':'https://doc.cfd.direct/notes/cfd-general-principles/turbulence-near-walls'},
 {'label':'Barkley, D., & Henderson, R. D. (1996). Three-dimensional Floquet stability analysis of the wake of a circular cylinder. Journal of Fluid Mechanics, 322, 215–241.','url':'https://doi.org/10.1017/S0022112096002777'},
 {'label':'OpenCFD. Turbulence mesh requirements (different OpenFOAM distribution; general wall-resolution guidance).','url':'https://doc.openfoam.com/2212/tools/processing/models/turbulence/'}]

MESH_KEYS=('dimension','xmin','xmax','ymin','ymax','depth','shapes','regions','mesh_method','radial','circumferential','spanwise','outer_radius','grading','cell_size','smoothing','manual_mesh')
def mesh_signature(project):
    data=asdict(project) if not isinstance(project,dict) else project
    mesh={k:data.get(k,{}) for k in MESH_KEYS}
    mesh['manual_blockMeshDict']=data.get('dictionary_overrides',{}).get('system/blockMeshDict')
    return hashlib.sha256(json.dumps(mesh,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def recommend(p,quality=None,metrics=None,goal='engineering',speed_of_sound=None,measured_yplus=None):
    if goal not in ('engineering','resolved'): raise ValueError('Unknown calculation goal.')
    length,source=reference(p); re=reynolds(p.velocity,length,p.viscosity); model=MODELS[p.turbulence]; messages=[]
    def add(code,severity,en,zh): messages.append({'code':code,'severity':severity,'en':en,'zh':zh})
    circle=not p.mesh_method.startswith('Manual topology') and len(p.shapes)==1 and p.shapes[0]['kind']=='circle' and abs(p.shapes[0]['width']-p.shapes[0]['height'])<1e-12
    cylinder_re=reynolds(p.velocity,p.shapes[0]['width'],p.viscosity) if circle else None
    preferred=None
    if circle:
        if cylinder_re<300: preferred='laminar'
        else: preferred='kOmegaSST' if goal=='engineering' else ('WALE' if p.dimension==3 and p.spanwise>=2 else None)
        if cylinder_re>=190:
            add('cylinder_3d','warning','Circular-cylinder wake can be three-dimensional from Re_D≈190. A 2D computation is an idealised benchmark/URANS approximation; assess span, span boundary conditions and resolution.','圆柱尾流在 Re_D≈190 起可能三维失稳。二维计算是理想化基准或二维 URANS 近似；需核对展向长度、边界和分辨率。')
        if cylinder_re>=1e5: add('high_re','warning','High-Re cylinder transition/separation and drag depend on roughness and inlet turbulence. Re alone cannot identify the regime, select transition seeds or certify drag.','高 Re 圆柱的转捩、分离和阻力取决于粗糙度与入口湍流；仅凭 Re 不能认定流态、设定转捩初值或保证阻力。')
        if source=='custom': add('custom_scale','info',f'Advice uses Re_D={cylinder_re:.6g} from geometric D; your displayed Re_L={re:.6g} uses custom L.','推荐按几何直径计算 Re_D；显示 Re_L 使用自定义 L，两者须区分。')
    else: add('geometry_scope','info','No automatic model choice for non-circular/multiple/empty geometries. Specify the flow type and validate against relevant data.','非圆柱、多实体或空流场不自动指定模型；须结合具体流型与基准数据。')
    if model.family in ('LES','Hybrid') or goal=='resolved':
        add('les_resolution','warning','LES/DES eligibility is not resolution adequacy. Assess near-wall/wake/filter resolution, resolved fluctuations, span boundaries, sampling and statistical convergence; cell count alone proves none of these.','三维准入不等于 LES/DES 分辨率达标。需检查近壁、尾流、滤波尺度、解析波动、展向边界、采样和统计收敛，不能凭网格总数认定。')
    if p.dimension==3 and circle:
        add('span_boundary','warning','Generated front/back boundaries are symmetryPlane, not periodic. Spanwise cell count does not establish a physically suitable cylinder-wake LES domain. Review actual boundary files in Expert tools.','当前生成的前后边界为 symmetryPlane，并非周期边界。展向层数不能证明圆柱 LES 计算域适合；请在专家工具核对实际边界文件。')
    blocked=False
    if quality is None:
        add('mesh_unknown','warning','Mesh quality is unknown for the current design. Generate/check this mesh before applying a model recommendation.','当前设计网格质量未知；生成并检查本设计网格后才可应用模型建议。')
    else:
        if quality.get('nonpositive_cells',0)>0: blocked=True; add('invalid_cells','error','Nonpositive cell volumes: repair the mesh; do not submit.','存在非正体积网格：须修复，禁止提交。')
        skew=quality.get('max_skewness',quality.get('skewness')); angle=quality.get('max_nonorthogonality_deg',quality.get('nonorthogonality'))
        if skew is None or angle is None: blocked=True; add('mesh_missing','error','Incomplete mesh metrics: no quality recommendation can be applied.','网格指标不完整，不能应用质量相关建议。')
        elif not math.isfinite(float(skew)) or not math.isfinite(float(angle)):
            blocked=True; add('mesh_nonfinite','error','Non-finite mesh metrics: repair/recheck mesh.','网格指标非有限值，须修复并重新检查。')
        elif skew>p.skew_limit or angle>p.nonortho_limit:
            blocked=True; add('mesh_quality','error',f'Skewness {skew:g} / non-orthogonality {angle:g}° exceeds project limits {p.skew_limit:g} / {p.nonortho_limit:g}°. Locate the worst faces and smooth/refine the transition.','skewness 或非正交角超过本项目阈值；定位最坏面并改善网格过渡。')
    add('wall_resolution','warning','y+ is unknown unless measured from this case. For wall-resolved models target y+ near 1 and verify layer resolution; log-layer wall functions need appropriate larger y+. Do not infer y+ from Re or total cells.','除非本算例实际测量，否则 y+ 未知。壁面解析通常以 y+ 接近 1 为目标并检查层数；对数层壁函数需适当更高 y+。不可从 Re 或总网格数推断 y+。')
    if quality and p.mesh_method=='Structured cylinder O-grid':
        expected=p.radial*p.circumferential*(p.spanwise if p.dimension==3 else 1)
        if quality.get('cells') is not None and quality['cells']!=expected:
            blocked=True; add('mesh_count_mismatch','error','Actual mesh cell count differs from this structured design. Inspect externally modified geometry/mesh; do not apply the suggestion.','实际网格数与当前结构网格设计不符，须检查外部修改；不能应用建议。')
    dt=None
    if metrics and metrics.get('uniform_flux_rate_per_velocity',0)>0:
        dt=p.max_co/(p.velocity*metrics['uniform_flux_rate_per_velocity'])
        add('time_estimate','info',f'Uniform-inlet geometric CFL estimate: dt≤{dt:.6g} s at Co={p.max_co:g}. This excludes acceleration/crossflow; retain adaptive stepping and check actual maximum Co.','依据真实网格与均匀入口速度估算 CFL 起始步长；不含加速与横向流动，仍须自适应并核对实际最大 Co。')
    if speed_of_sound is None: add('mach_unknown','warning','Mach number is unknown. Re=10^7 does not establish incompressibility; supply a physical speed of sound and check U/a before using this incompressible solver.','马赫数未知。Re=10⁷ 不代表可用不可压缩求解器；需提供实际声速并检查 U/a。')
    else:
        from .reynolds import positive
        mach=p.velocity/positive(speed_of_sound,'Speed of sound')
        if mach>=.3: blocked=True; add('mach','error',f'Mach={mach:.4g}≥0.3: this incompressible workflow is not recommended. Select a validated compressible solver externally.','Ma≥0.3：不推荐本不可压缩流程，应使用经验证的可压缩求解器。')
        else: add('mach','info',f'Mach={mach:.4g}; this is a screening check, not a compressibility-error estimate.','马赫数筛查通过，但不是压缩性误差估计。')
    if measured_yplus is not None: add('yplus_measured','info',f'Supplied measured y+={measured_yplus:g}; verify provenance and distribution, not only one value.','已提供实测 y+；需核对来源及分布，不能仅凭一个值。')
    if p.dictionary_overrides: add('overrides','warning','Dictionary overrides may supersede generated physics. Review actual U, viscosity, model and numerical dictionaries; recommendation does not clear them.','字典覆盖可能取代界面物理设置，须核对实际 U、黏度、模型和数值字典；推荐不会自动清除。')
    add('heuristic','info','Recommendations are explicit engineering starting points, not a universal Re-to-model law. Apply only after reviewing the evidence; geometry and time controls are unchanged.','建议为明确标注的工程起点，并非通用 Re→模型定律。核对证据后才应用；不更改几何和时间设置。')
    return {'re':re,'reference_length_m':length,'reference_source':source,'cylinder_re_D':cylinder_re,'preferred_model':preferred,'goal':goal,'messages':messages,'blocked':blocked,'quality':quality,'metrics':metrics,'estimated_start_dt_s':dt,'sources':SOURCES}
