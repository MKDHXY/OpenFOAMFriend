"""Per-field scientific lookup tables and explicit scalar-bar controls."""
import copy,math
from dataclasses import dataclass,asdict
import numpy as np
import vtk
from matplotlib import colormaps
from PySide6.QtWidgets import *
from .i18n import text,preferences,save_preference

PALETTES={'Viridis':'viridis','Cividis':'cividis','Blue–red':'coolwarm','Grey':'gray','Rainbow (legacy)':'jet','Turbo':'turbo'}

@dataclass
class ColourSettings:
    palette:str='Viridis'
    reverse:bool=False
    auto_range:bool=True
    minimum:float=0.
    maximum:float=1.
    logarithmic:bool=False
    visible:bool=True
    title:str=''
    labels:int=5
    precision:int=3
    notation:str='g'
    font_size:int=12
    title_size:int=16
    orientation:str='vertical'
    x:float=.86
    y:float=.15
    width:float=.12
    height:float=.65
    colours:int=256
    def validate(self):
        if self.palette not in PALETTES or self.orientation not in ('vertical','horizontal') or self.notation not in ('g','e','f'): raise ValueError('Unknown colour-map setting.')
        if not all(math.isfinite(v) for v in (self.minimum,self.maximum,self.x,self.y,self.width,self.height)): raise ValueError(text('All numeric settings must be finite.','所有数值必须为有限数。'))
        if not self.auto_range and self.minimum>=self.maximum: raise ValueError(text('Minimum must be smaller than maximum.','最小值必须小于最大值。'))
        if self.logarithmic and not self.auto_range and self.minimum<=0: raise ValueError(text('Logarithmic colour scale requires positive limits.','对数色标要求范围为正值。'))
        if self.logarithmic and self.auto_range: raise ValueError(text('Use a positive fixed range for logarithmic scale, so playback cannot cross zero.','对数色标请使用正值固定范围，避免播放时跨过零值。'))
        if not (0<=self.x<1 and 0<=self.y<1 and 0<self.width<=1-self.x+1e-9 and 0<self.height<=1-self.y+1e-9): raise ValueError(text('Colour bar must fit inside the viewport (x+width ≤1, y+height ≤1).','色标必须位于视口内：x+宽度≤1，y+高度≤1。'))
        if not (2<=self.labels<=12 and 1<=self.precision<=10 and 8<=self.font_size<=36 and 8<=self.title_size<=40 and 16<=self.colours<=512): raise ValueError('Invalid label, font or colour count.')

def settings_for(name):
    data=preferences().get('colour_maps',{}).get(name,{})
    try: settings=ColourSettings(**data); settings.validate(); return settings
    except (ValueError,TypeError): return ColourSettings()

def save_settings(name,settings):
    settings.validate(); values=preferences().get('colour_maps',{}); values[name]=asdict(settings); save_preference('colour_maps',values)

def apply_lookup(mapper,bar,settings,data_range,name):
    settings.validate(); low,high=data_range if settings.auto_range else (settings.minimum,settings.maximum)
    if not math.isfinite(low) or not math.isfinite(high) or high<low: raise ValueError('No finite scalar range is available.')
    if low==high:
        epsilon=max(abs(low)*1e-6,1e-12); low-=epsilon; high+=epsilon
    if settings.logarithmic and low<=0: raise ValueError(text('This field contains zero/negative values. Use linear scale or a positive fixed range.','该场含零或负值，请使用线性色标或正值固定范围。'))
    lut=vtk.vtkLookupTable(); lut.SetNumberOfTableValues(settings.colours); lut.SetTableRange(low,high)
    lut.SetScaleToLog10() if settings.logarithmic else lut.SetScaleToLinear(); lut.Build()
    colours=colormaps[PALETTES[settings.palette]](np.linspace(1,0,settings.colours) if settings.reverse else np.linspace(0,1,settings.colours))
    for index,rgba in enumerate(colours): lut.SetTableValue(index,*map(float,rgba))
    lut.SetVectorModeToMagnitude(); mapper.SetLookupTable(lut); mapper.UseLookupTableScalarRangeOn(); mapper.SetScalarRange(low,high)
    bar.SetLookupTable(lut); bar.SetTitle(settings.title.strip() or name); bar.SetVisibility(settings.visible); bar.SetNumberOfLabels(settings.labels); bar.SetLabelFormat(f'%.{settings.precision}{settings.notation}')
    bar.SetOrientationToVertical() if settings.orientation=='vertical' else bar.SetOrientationToHorizontal()
    bar.SetPosition(settings.x,settings.y); bar.SetWidth(settings.width); bar.SetHeight(settings.height); bar.SetUnconstrainedFontSize(True)
    bar.GetLabelTextProperty().SetFontSize(settings.font_size); bar.GetTitleTextProperty().SetFontSize(settings.title_size)
    return (low,high)

class ColourMapDialog(QDialog):
    def __init__(self,viewer,parent=None):
        super().__init__(parent or viewer); self.viewer=viewer; self.key=viewer.colour_key; self.setWindowTitle(text('Colour map & legend — ','配色与色标 — ')+self.key); self.resize(480,660)
        box=QVBoxLayout(self); self.notice=QLabel(); self.notice.setWordWrap(True); box.addWidget(self.notice)
        tabs=QTabWidget(); box.addWidget(tabs); self.inputs={}
        for heading,keys in [(text('Colour & range','配色与范围'),('palette','reverse','auto_range','minimum','maximum','logarithmic','colours')),(text('Legend & layout','色标与布局'),('visible','title','labels','precision','notation','font_size','title_size','orientation','x','y','width','height'))]:
            page=QWidget(); form=QFormLayout(page); tabs.addTab(page,heading)
            labels={'palette':text('Palette','配色'),'reverse':text('Reverse colours','反转颜色'),'auto_range':text('Auto: current frame','自动：当前帧'),'minimum':text('Fixed minimum','固定最小值'),'maximum':text('Fixed maximum','固定最大值'),'logarithmic':text('Logarithmic (positive only)','对数（仅正值）'),'colours':text('Colour resolution','颜色数量'),'visible':text('Show legend','显示色标'),'title':text('Title (blank = field)','标题（空白为场名）'),'labels':text('Tick count','刻度数量'),'precision':text('Numeric precision','数值精度'),'notation':text('Number format','数字格式'),'font_size':text('Tick font / px','刻度字号 / px'),'title_size':text('Title font / px','标题字号 / px'),'orientation':text('Orientation','方向'),'x':text('Left / viewport fraction','左侧位置 / 视口比例'),'y':text('Bottom / viewport fraction','底部位置 / 视口比例'),'width':text('Width / viewport fraction','宽度 / 视口比例'),'height':text('Height / viewport fraction','高度 / 视口比例')}
            for key in keys:
                if key in ('palette','orientation','notation'):
                    inp=QComboBox()
                    values=[(p,p) for p in PALETTES] if key=='palette' else [(text('Vertical','竖直'),'vertical'),(text('Horizontal','水平'),'horizontal')] if key=='orientation' else [(text('General','通用'),'g'),(text('Scientific','科学计数'),'e'),(text('Fixed decimal','固定小数'),'f')]
                    for label,value in values: inp.addItem(label,value)
                elif key in ('reverse','auto_range','logarithmic','visible'): inp=QCheckBox()
                elif key in ('title','minimum','maximum'): inp=QLineEdit(); inp.setPlaceholderText('1e-12' if key!='title' else '')
                elif key in ('labels','precision','font_size','title_size','colours'):
                    inp=QSpinBox(); bounds={'labels':(2,12),'precision':(1,10),'font_size':(8,36),'title_size':(8,40),'colours':(16,512)}; inp.setRange(*bounds[key])
                else:
                    inp=QDoubleSpinBox(); inp.setDecimals(10 if key in ('minimum','maximum') else 3); inp.setRange(-1e100,1e100) if key in ('minimum','maximum') else inp.setRange(0,1); inp.setSingleStep(.01)
                self.inputs[key]=inp; form.addRow(labels[key],inp)
        freeze=QPushButton(text('Use current data range as fixed limits','将当前数据范围设为固定色标')); freeze.clicked.connect(self.freeze_current_range); box.addWidget(freeze)
        self.fill(viewer.colour_settings.get(self.key,settings_for(self.key)))
        self.inputs['auto_range'].toggled.connect(self.range_controls); self.inputs['orientation'].currentIndexChanged.connect(self.orientation_preset)
        self.range_controls(); self.notice.setText(text(f'Field: {self.key} · actual range {viewer.colour_range[0]:.6g} … {viewer.colour_range[1]:.6g}. Fixed limits stay unchanged during playback. Outside-range values use end colours. Position is measured from the viewport bottom-left. Changes affect display and PNG/GIF, not CFD data.','场：'+self.key+f' · 实际范围 {viewer.colour_range[0]:.6g} … {viewer.colour_range[1]:.6g}。固定范围播放时保持不变，超范围值使用端点颜色。位置从视口左下角计算。修改影响显示及 PNG/GIF，不修改 CFD 数据。'))
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Apply|QDialogButtonBox.Cancel|QDialogButtonBox.RestoreDefaults); buttons.accepted.connect(lambda:self.apply_settings(close=True)); buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings); buttons.rejected.connect(self.reject); buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(lambda:self.fill(ColourSettings())); box.addWidget(buttons)
    def fill(self,settings):
        for key,inp in self.inputs.items():
            value=getattr(settings,key); inp.blockSignals(True)
            if isinstance(inp,QComboBox): inp.setCurrentIndex(inp.findData(value))
            elif isinstance(inp,QCheckBox): inp.setChecked(value)
            elif isinstance(inp,QLineEdit): inp.setText(str(value) if key=='title' else format(value,'.16g'))
            else: inp.setValue(value)
            inp.blockSignals(False)
        self.range_controls()
    def range_controls(self,*args):
        for key in ('minimum','maximum'): self.inputs[key].setEnabled(not self.inputs['auto_range'].isChecked())
    def orientation_preset(self,*args):
        horizontal=self.inputs['orientation'].currentData()=='horizontal'
        for key,value in zip(('x','y','width','height'),(.15,.02,.65,.12) if horizontal else (.86,.15,.12,.65)): self.inputs[key].setValue(value)
    def freeze_current_range(self):
        low,high=self.viewer.colour_range
        if low==high:
            epsilon=max(abs(low)*1e-6,1e-12); low-=epsilon; high+=epsilon
        self.inputs['auto_range'].setChecked(False)
        self.inputs['minimum'].setText(format(low,'.16g')); self.inputs['maximum'].setText(format(high,'.16g'))
    def values(self):
        values={key:inp.currentData() if isinstance(inp,QComboBox) else inp.isChecked() if isinstance(inp,QCheckBox) else (inp.text() if key=='title' else float(inp.text())) if isinstance(inp,QLineEdit) else inp.value() for key,inp in self.inputs.items()}; settings=ColourSettings(**values); settings.validate(); return settings
    def apply_settings(self,*args,close=False):
        try:
            settings=self.values()
            # Validate actual auto-range/log compatibility before committing.
            effective=self.viewer.colour_range if settings.auto_range else (settings.minimum,settings.maximum)
            if settings.logarithmic and effective[0]<=0: raise ValueError(text('Log scale requires positive data/limits.','对数色标要求数据或固定范围为正值。'))
            self.viewer.colour_settings[self.key]=copy.deepcopy(settings); self.viewer.apply_colour_map(); save_settings(self.key,settings); self.viewer.info.emit(text('Colour map applied: ','色标已应用：')+self.key)
            if close: self.accept()
        except Exception as e: QMessageBox.warning(self,text('Invalid colour map','色标设置无效'),str(e))
