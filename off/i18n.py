"""Runtime UI translation; canonical OpenFOAM keys and project values stay intact."""
import os,json
from pathlib import Path
LANG='en'
PAIRS={
'Transient incompressible solver / SI':'瞬态不可压缩求解器 / SI',
'Sa Viscosity Ratio':'SA 初始 nuTilda/nu 比值','Transition Retheta':'转捩 ReThetat 初值','Intermittency':'间歇因子 gammaInt 初值','Dynamic Seed':'动态平均量初值 / m4·s⁻4',
'Object snap F3':'对象吸附 F3','Ortho F8':'正交 F8','Grid snap F9':'网格吸附 F9',
'Line':'直线','Polyline':'折线','Exact line':'精确直线','Mesh spacing':'网格间距','Initial fields / dictionaries':'初始场 / 字典','SSH / Slurm supercomputer':'SSH / Slurm 超算',
'01  GEOMETRY':'01  几何','02  SCENES':'02  场景','Simulation objects':'仿真对象','Simulation tree':'仿真树','Guided workflow':'引导式流程',
'Snap Spacing M':'吸附间距 / m（0 为关闭）','Display Unit':'标尺显示单位','Xmin':'x 最小值 / m','Xmax':'x 最大值 / m','Ymin':'y 最小值 / m','Ymax':'y 最大值 / m',
'Project':'项目','Postprocess':'后处理','Help':'帮助','Settings':'设置','Language / 语言':'语言 / Language',
'Select':'选择','Pan':'平移','Circle':'圆','Rectangle':'矩形','Triangle':'三角形','Mesh region':'网格区域','Eraser':'橡皮','Measure':'测量','Undo':'撤销','Redo':'重做','Fit':'适配视图','Cylinder preset':'圆柱预设','Submit':'提交计算',
'Design tree':'设计对象','Properties & workflow':'参数与流程','Evidence / solver log':'证据与求解日志','Project objects / SI dimensions':'项目对象 / SI 尺寸',
'01  GEOMETRY & MESH':'01  几何与网格','02  MESH & RESULTS':'02  网格与结果','03  RUN QUEUE':'03  计算队列',
'Submit design':'提交设计','Pause':'暂停','Continue':'继续','Recover checkpoint':'恢复检查点','Cancel':'取消','Earlier':'提前','Later':'延后','Open result':'查看结果','Folder':'打开文件夹','Refresh':'刷新',
'Domain & dimension':'流场范围与维度','Mesh generation settings':'手动网格设置','Flow & solver settings':'流动与求解设置','WSL connection & CPU budget':'WSL 连接与核心预算','Generate / check mesh only':'直接生成并检查网格','Locate worst skewness':'定位最坏偏斜面','Locate worst non-orthogonality':'定位最坏非正交面','View / edit case dictionaries':'OpenFOAM 参数与代码',
'New cylinder project':'新建圆柱项目','Open project…':'打开项目…','Save project…':'保存项目…','Import .foam result…':'导入 .foam 结果…','Open WSL run folder':'打开 WSL 算例目录','WSL configuration…':'WSL 配置…','Exit':'退出',
'Export screenshot PNG…':'导出视图 PNG…','Export real-frame GIF…':'导出真实帧 GIF…','Export configurable CSV…':'自定义 CSV 导出…','Export PINN MAT…':'导出 PINN MAT…','Force history & single-sided FFT':'力系数历史与单边 FFT','User guide EN':'英文使用手册','使用说明 中文':'中文使用手册','About':'关于',
'Case':'算例','Stage':'阶段','Cores':'核心数','Simulated t / s':'模拟时间 / s','Progress':'进度','Max Co (latest)':'最新最大 Co','Elapsed':'已耗时','ETA estimate':'预计剩余','Mesh quality':'网格质量',
'Automatic mesh assistant':'自动网格助手','Precise shape':'精确绘制','Sketch settings':'绘图设置','Website support':'帮助网站','Reset workspace layout':'重置界面布局',
'Edges':'边线','Full volume':'全体积','XY mid-slice':'XY 中截面','XZ mid-slice':'XZ 中截面','YZ mid-slice':'YZ 中截面','Mesh':'网格','Load a real .foam case':'请载入真实 .foam 算例',
'Geometry / solid obstacles':'几何 / 实体障碍物','Mesh control regions':'网格控制区域','Name':'名称','Dimension':'维度','Depth':'厚度 / m','Velocity':'入口速度 / m·s⁻¹','Viscosity':'运动黏度 / m²·s⁻¹','End Time':'结束时间 / s','Delta T':'最大内部时间步 / s','Write Interval':'场保存间隔 / s','Max Co':'最大 Courant 数','Mesh Method':'网格方法','Radial':'径向单元数','Circumferential':'圆周单元数','Spanwise':'展向单元数','Outer Radius':'外边界半径 / m','Grading':'末格 / 首格膨胀比','Cell Size':'背景目标尺寸 / m','Smoothing':'平滑迭代数','Nonortho Limit':'非正交角阈值 / °','Skew Limit':'偏斜度阈值','Turbulence':'湍流模型','Turbulence Intensity':'湍流强度 / 比例','Turbulence Length':'湍流尺度 / m','Distro':'WSL 发行版','Bashrc':'OpenFOAM 环境脚本','Run Dir':'Linux 算例目录','Max Cores':'总核心预算','Poll Seconds':'轮询间隔 / s','Width':'宽度 / 直径 / m','Height':'高度 / m','Size':'目标尺寸 / m','Direction':'渐变方向','Ratio':'尺寸比值','Kind':'几何类型','Row Stride':'每隔几行导出','Times':'导出时间范围','Columns':'导出列名',
'Structured cylinder O-grid':'结构圆柱 O 型网格','Structured partitioned box':'结构分区矩形网格','Gmsh triangle / prism':'自动三角形 / 棱柱','Gmsh quadrilateral / prism':'自动四边形为主 / 混合体','Gmsh tetrahedral':'自动三维四面体','uniform':'均匀','current':'当前时刻','all':'全部时刻','circle':'圆','rectangle':'矩形','triangle':'三角形',
'Domain / SI metres':'流场设置 / 单位米','Meshing':'手动网格参数','Transient incompressible solver / SI':'瞬态不可压求解设置 / SI','Machine-specific WSL profile':'当前电脑 WSL 配置','Object dimensions / mesh control':'对象尺寸 / 网格区域设置','CSV columns / row stride':'CSV 列与行间隔',
'Operation failed':'操作失败','Working':'正在处理','OK':'确定','Save':'保存','Close':'关闭',
'QUEUED':'排队中','STARTING':'启动中','MESHING':'生成网格','CHECKING':'检查网格','RUNNING':'运行中','PAUSED':'已暂停','EXPORTING':'导出中','DONE':'已完成','FAILED':'失败','CANCELLED':'已取消','STALLED':'需检查恢复','PASS':'通过',
}
PAIRS.update({'Design parameters / mesh code':'设计参数 / 网格代码','Welcome / Projects':'欢迎 / 项目管理','Detect WSL / OpenFOAM':'自动探测 WSL / OpenFOAM','WSL Terminal':'WSL 终端','Export complete .foam case folder':'导出完整 .foam 算例文件夹','Orthographic / 正交投影':'正交投影 / Orthographic'})

def settings_path(): return Path(os.getenv('APPDATA',str(Path.home())))/'OpenFoamFriend'/'ui.json'

def preferences():
    p=settings_path()
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}

def save_preference(key,value):
    data=preferences(); data[key]=value; p=settings_path(); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data),encoding='utf-8')
def initialize():
    global LANG
    p=settings_path(); LANG=os.getenv('OFF_LANGUAGE') or (json.loads(p.read_text(encoding='utf-8')).get('language','en') if p.exists() else 'zh')
def tr(text): return PAIRS.get(text,text) if LANG=='zh' else text
def text(en,zh): return zh if LANG=='zh' else en
def set_language(lang):
    global LANG
    LANG=lang; save_preference('language',lang)
def translate_widgets(root):
    from PySide6.QtWidgets import QPushButton,QCheckBox,QLabel,QDockWidget,QTabWidget,QTreeWidget,QTableWidget,QMenu,QDialogButtonBox
    from PySide6.QtGui import QAction
    for w in [root]+root.findChildren(QPushButton)+root.findChildren(QCheckBox)+root.findChildren(QLabel)+root.findChildren(QAction)+root.findChildren(QDockWidget)+root.findChildren(QMenu):
        if isinstance(w,(QDockWidget,QMenu)): getter=w.windowTitle if isinstance(w,QDockWidget) else w.title; setter=w.setWindowTitle if isinstance(w,QDockWidget) else w.setTitle
        elif hasattr(w,'text') and hasattr(w,'setText'): getter=w.text; setter=w.setText
        else: continue
        original=w.property('off_original')
        if original is None:
            original=getter()
            if original not in PAIRS: continue
            w.setProperty('off_original',original)
        setter(tr(original))
    for tabs in root.findChildren(QTabWidget):
        original=tabs.property('off_titles') or [tabs.tabText(i) for i in range(tabs.count())]; tabs.setProperty('off_titles',original)
        for i,value in enumerate(original): tabs.setTabText(i,tr(value))
    for tree in root.findChildren(QTreeWidget):
        for i in range(tree.columnCount()):
            item=tree.headerItem(); original=item.data(i,0x100+20) or item.text(i); item.setData(i,0x100+20,original); item.setText(i,tr(original))
    for table in root.findChildren(QTableWidget):
        for i in range(table.columnCount()):
            item=table.horizontalHeaderItem(i)
            if item: original=item.data(0x100+20) or item.text(); item.setData(0x100+20,original); item.setText(tr(original))

PAIRS.update({'Expert tools…':'专家工具…','Reynolds number & scaling':'雷诺数与联动设置','Workflow:':'工作方式：'})

PAIRS.update({'Polygon solid':'多边形实体','Polygon':'多边形','Generated design files':'生成设计文件','Meshing operations':'网格操作','Mesh region':'加密区域控制'})

PAIRS.update({'Files':'文件','Generated design files…':'生成设计文件…','Selected case — all files…':'所选算例全部文件…','Application source — all files…':'软件全部源码…','Typical flow starters…':'典型流场模板…','Quick tutorials…':'快速教程…','Draw refinement region':'绘制加密区域'})
PAIRS.update({'OpenFOAM run directory — all files…':'OpenFOAM 算例目录全部文件…'})
