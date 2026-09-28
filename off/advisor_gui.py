"""Read-only evidence report with explicitly gated model application."""
import copy,json
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QTextBrowser,QCheckBox,QDialogButtonBox
from .i18n import text
from .advisor import recommend

class AdviceDialog(QDialog):
    def __init__(self,project,evidence,parent=None):
        super().__init__(parent); self.project=project; self.evidence=evidence; self.result_project=None; self.setWindowTitle(text('Re / mesh setup advisor','Re / 网格设置建议')); self.resize(780,650)
        box=QVBoxLayout(self); row=QHBoxLayout(); box.addLayout(row); row.addWidget(QLabel(text('Calculation goal','计算目标'))); self.goal=QComboBox(); self.goal.addItem(text('Engineering mean / URANS comparison','工程均值 / URANS 对比'),'engineering'); self.goal.addItem(text('Resolve 3D wake fluctuations (LES candidate)','解析三维尾流波动（LES 候选）'),'resolved'); row.addWidget(self.goal)
        from .numeric_controls import ScientificSpin
        self.mach_check=QCheckBox(text('Physical speed of sound available','已知实际声速')); self.sound_speed=ScientificSpin(); self.sound_speed.setRange(1e-10,1e7); self.sound_speed.setValue(340.); self.sound_speed.setEnabled(False); mach_row=QHBoxLayout(); mach_row.addWidget(self.mach_check); mach_row.addWidget(QLabel('a / m·s⁻¹')); mach_row.addWidget(self.sound_speed); box.addLayout(mach_row)
        self.report=QTextBrowser(); self.report.setOpenExternalLinks(True); box.addWidget(self.report)
        self.review=QCheckBox(text('I reviewed the model, wall treatment, mesh and required initial fields.','我已核对模型、壁面处理、网格与所需初始场。')); box.addWidget(self.review)
        self.apply_button=QPushButton(text('Apply proposed model only','仅应用建议模型')); self.apply_button.clicked.connect(self.apply); box.addWidget(self.apply_button)
        buttons=QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject); box.addWidget(buttons)
        self.mach_check.toggled.connect(lambda checked:(self.sound_speed.setEnabled(checked),self.refresh())); self.sound_speed.valueChanged.connect(self.refresh); self.goal.currentIndexChanged.connect(self.refresh); self.review.toggled.connect(self.enable_apply); self.refresh()
    def refresh(self):
        import html
        evidence=self.evidence or {}; self.advice=recommend(self.project,evidence.get('quality'),evidence.get('metrics'),self.goal.currentData(),speed_of_sound=self.sound_speed.value() if self.mach_check.isChecked() else None)
        a=self.advice; parts=['<h3>'+text('Setup screening','设置筛查')+'</h3>',f'<p>Re<sub>L</sub>={a["re"]:.9g}; L={a["reference_length_m"]:.9g} m; U={self.project.velocity:g} m/s; nu={self.project.viscosity:g} m²/s</p>']
        proposed=a['preferred_model'] or text('No automatic selection','不自动指定'); parts.append('<p>'+text('Proposed starting model: ','建议起始模型：')+proposed+'</p>')
        if evidence.get('case'): parts.append('<p>'+text('Measured mesh case: ','实测网格算例：')+html.escape(evidence['case'])+'</p>')
        if a['quality']: parts.append('<pre>'+html.escape(json.dumps(a['quality'],indent=2,ensure_ascii=False))+'</pre>')
        if a['metrics']: parts.append('<pre>'+html.escape(json.dumps(a['metrics'],indent=2,ensure_ascii=False))+'</pre>')
        for message in a['messages']: parts.append('<p><b>'+html.escape(message['severity'].upper())+'</b> · '+html.escape(text(message['en'],message['zh']))+'</p>')
        parts.append('<h4>'+text('Sources and scope','来源与适用范围')+'</h4>')
        for source in a['sources']: parts.append('<p><a href="'+source['url']+'">'+html.escape(source['label'])+'</a></p>')
        self.report.setHtml(''.join(parts)); self.review.setChecked(False); self.enable_apply()
    def enable_apply(self):
        self.apply_button.setEnabled(self.review.isChecked() and self.evidence is not None and self.advice['preferred_model'] is not None and not self.advice['blocked'] and not self.project.dictionary_overrides)
    def apply(self):
        if not self.apply_button.isEnabled(): return
        result=copy.deepcopy(self.project); result.turbulence=self.advice['preferred_model']
        try: result.validate()
        except ValueError as e: self.report.append('<p>'+str(e)+'</p>'); return
        self.result_project=result; super().accept()
