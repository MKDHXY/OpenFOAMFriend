"""Remote submitter with exact script preview and durable scheduler records."""
from pathlib import Path
from dataclasses import asdict
import json
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
from .ssh_backend import *
from .dictionary_editor import CodeEditor
from .backend import DATA
from .i18n import text

class SSHDialog(QDialog):
    def __init__(self,parent):
        super().__init__(parent); self.owner=parent; self.setWindowTitle(text('SSH / Slurm supercomputer','SSH / Slurm 超算')); self.resize(1000,720); self.pending=False; self.config=load_cluster(); self.records_path=DATA/'remote_jobs.json'; self.records=json.loads(self.records_path.read_text()) if self.records_path.exists() else []; self.inputs={}
        box=QVBoxLayout(self); tabs=QTabWidget(); box.addWidget(tabs); config=QWidget(); form=QFormLayout(config)
        for key,value in asdict(self.config).items():
            if key=='launcher': widget=QComboBox(); widget.addItems(['srun','mpirun']); widget.setCurrentText(value)
            elif isinstance(value,int): widget=QSpinBox(); widget.setRange(30 if key=='poll_seconds' else 1,65535); widget.setValue(value)
            else: widget=QLineEdit(value)
            labels={'host':'主机 / SSH 配置别名','user':'用户名','port':'端口','identity':'本机密钥路径（留空用代理）','remote_root':'远程算例根目录','environment':'OpenFOAM 环境加载命令','partition':'分区','account':'账户 / 项目','walltime':'最长运行时间','cores':'MPI 进程数','launcher':'MPI 启动器','poll_seconds':'轮询间隔 / 秒'}
            self.inputs[key]=widget; form.addRow(text(key.replace('_',' ').title(),labels[key]),widget)
        info=QLabel(text('Slurm only in this release. Use SSH config alias / key / agent; passwords are not stored. Host must already be verified in known_hosts. Environment and MPI launcher depend on your cluster. Pending jobs support hold/release; running-job suspend may require administrator rights and is not offered.','本版支持 Slurm。使用 SSH 别名 / 密钥 / 代理，不保存密码。主机须已在 known_hosts 中验证。环境命令和 MPI 启动器按超算配置。排队作业可 hold/release；运行中暂停可能需管理员权限，本版不提供。')); info.setWordWrap(True); form.addRow(info)
        self.help=QTextBrowser(); self.help.setMaximumHeight(170); self.help.setHtml(text('<b>Configuration sequence</b><ol><li>Use the login host and username supplied by your cluster. Test SSH in a terminal first and verify the host fingerprint with the site.</li><li>Choose your existing local key, or leave Identity empty to use ssh-agent. No password is stored.</li><li>Set a writable remote scratch directory and the site OpenFOAM module/source command.</li><li>Set partition/account, walltime and ranks within your allocation. Choose the MPI launcher required by the site.</li><li>Save &amp; test checks foamRun, sbatch and squeue. Review the exact batch script before submitting.</li></ol>Monitoring continues when this dialog is hidden while the application is open. Remote jobs continue if the application exits; reopen this panel to resume monitoring. Slurm only; no PBS support.','<b>配置顺序</b><ol><li>填写超算提供的登录主机与用户名。先在终端登录，并向超算核对主机指纹。</li><li>选择已有本机密钥；使用 ssh-agent 可留空。不保存密码。</li><li>填写有写权限的远程 scratch 目录，以及该超算的 OpenFOAM module/source 命令。</li><li>按配额填写分区、项目账户、时限及进程数，选择超算规定的 MPI 启动器。</li><li>保存并测试会检查 foamRun、sbatch、squeue；提交前审阅完整脚本。</li></ol>主程序开启时，隐藏此窗口仍继续监控。退出主程序不会取消远程作业，重新打开此面板恢复监控。仅支持 Slurm，不支持 PBS。')); form.addRow(self.help)
        test=QPushButton(text('Save & test connection','保存并测试连接')); test.clicked.connect(self.test); form.addRow(test); config_scroll=QScrollArea(); config_scroll.setWidgetResizable(True); config_scroll.setWidget(config); tabs.addTab(config_scroll,text('1 Connection','1 连接'))
        submission=QWidget(); layout=QVBoxLayout(submission); row=QHBoxLayout(); self.case=QLineEdit(); row.addWidget(self.case); browse=QPushButton(text('Choose inactive case','选择非活动算例')); browse.clicked.connect(self.browse); row.addWidget(browse); layout.addLayout(row)
        preview=QPushButton(text('Generate batch script preview','生成批处理脚本预览')); preview.clicked.connect(self.preview); layout.addWidget(preview); self.script=CodeEditor(); layout.addWidget(self.script)
        submit_button=QPushButton(text('Upload 0 / system / constant & submit reviewed script','上传 0 / system / constant 并提交审阅脚本')); submit_button.clicked.connect(self.submit); layout.addWidget(submit_button); tabs.addTab(submission,text('2 Preview & submit','2 预览与提交'))
        jobs=QWidget(); layout=QVBoxLayout(jobs); self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels([text('Job ID','作业编号'),text('Cluster','集群'),text('Case','算例'),text('Status','状态'),text('Elapsed','已用时间'),text('Scheduler details','调度信息')]); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); layout.addWidget(self.table)
        row=QHBoxLayout()
        for en,zh,fn in [('Refresh','刷新',self.refresh),('Hold pending','暂停排队',lambda:self.control('hold')),('Release pending','继续排队',lambda:self.control('release')),('Cancel job','取消作业',lambda:self.control('cancel'))]: button=QPushButton(text(en,zh)); button.clicked.connect(fn); row.addWidget(button)
        layout.addLayout(row); tabs.addTab(jobs,text('3 Scheduler jobs','3 调度作业')); self.output=QPlainTextEdit(); self.output.setReadOnly(True); self.output.setMaximumBlockCount(1000); self.output.setMaximumHeight(150); box.addWidget(self.output); self.output.setPlainText(text('No remote connection or job has been validated yet. Probe is read-only. Submission requires a reviewed script and incurs cluster compute usage.','尚未验证远程连接或作业。连接测试只读。提交需要审阅脚本，并占用超算计算资源。')); self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.draw(); self.timer.start(self.config.poll_seconds*1000) if self.records else None
    def values(self):
        c=Cluster(**{key:widget.currentText() if isinstance(widget,QComboBox) else widget.value() if isinstance(widget,QSpinBox) else widget.text() for key,widget in self.inputs.items()}); c.validate(); return c
    def run(self,fn,done=None):
        if self.pending or getattr(self,'worker',None) is not None: return
        self.pending=True
        def success(value): self.pending=False; self.output.appendPlainText(str(value)); done(value) if done else None
        from .gui import Worker
        w=Worker(fn,self); self.worker=w; w.success.connect(success); w.error.connect(lambda e:(setattr(self,'pending',False),self.output.appendPlainText(e)))
        def finished():
            if self.worker is w: self.worker=None
            w.deleteLater()
        w.finished.connect(finished); w.start()
    def test(self):
        try: c=self.values(); save_cluster(c); self.run(lambda:probe(c))
        except Exception as e: self.output.appendPlainText(str(e))
    def browse(self):
        path=QFileDialog.getExistingDirectory(self,text('Choose case folder','选择算例目录'))
        if path: self.case.setText(path)
    def preview(self):
        try: self.script.setPlainText(batch_script(self.values(),Path(self.case.text()).name))
        except Exception as e: self.output.appendPlainText(str(e))
    def submit(self):
        try:
            c=self.values(); path=Path(self.case.text()); script=self.script.toPlainText()
            if not script.startswith('#!/bin/bash'): raise ValueError('Generate and review the batch script first.')
            if any(Path(j['case'])==path and j['state'] not in ('DONE','FAILED','CANCELLED') for j in self.owner.engine.store.all()): raise ValueError('Selected case is active locally.')
            if QMessageBox.question(self,text('Submit reviewed batch script','提交审阅脚本'),text(f'Submit {path.name} to {c.host} using {c.cores} ranks?\nThe script shown will execute remotely.',f'将 {path.name} 用 {c.cores} 个进程提交至 {c.host}？\n将执行当前预览脚本。'))!=QMessageBox.Yes: return
            save_cluster(c)
            def done(j): self.records.append(j); self.persist(); self.draw(); self.timer.start(c.poll_seconds*1000)
            self.run(lambda:submit(c,path,script,DATA),done)
        except Exception as e: self.output.appendPlainText(str(e))
    def persist(self): self.records_path.write_text(json.dumps(self.records,indent=2),encoding='utf-8')
    def draw(self):
        self.table.setRowCount(len(self.records))
        for row,j in enumerate(self.records):
            for col,value in enumerate((j['job_id'],j['cluster']['host'],j['remote_case'],j.get('state','UNKNOWN'),j.get('elapsed','—'),j.get('scheduler_detail','—'))): self.table.setItem(row,col,QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
    def refresh(self):
        if not self.records or self.pending: return
        def fetch():
            groups={}
            for j in self.records: groups.setdefault(json.dumps(j['cluster'],sort_keys=True),[]).append(j['job_id'])
            return {key:query(Cluster(**json.loads(key)),ids) for key,ids in groups.items()}
        def done(outputs):
            for j in self.records:
                raw=outputs[json.dumps(j['cluster'],sort_keys=True)]; rows=[line.split('|') for line in raw.splitlines() if line.startswith(j['job_id']+'|')]
                j['state']=rows[-1][1] if rows else 'UNKNOWN'; j['elapsed']=rows[-1][2] if rows and len(rows[-1])>2 else '—'; j['scheduler_detail']=' | '.join(rows[-1][3:]) if rows else '—'; j['scheduler_output']=raw; j['checked']=time.time()
            self.persist(); self.draw()
        self.run(fetch,done)
    def control(self,action):
        row=self.table.currentRow()
        if row<0: return
        j=self.records[row]
        if action=='cancel' and QMessageBox.question(self,text('Cancel','取消'),f"scancel {j['job_id']} ?")!=QMessageBox.Yes: return
        self.run(lambda:control(Cluster(**j['cluster']),j['job_id'],action))
    def closeEvent(self,e):
        self.hide(); e.ignore()
    def reject(self):
        self.hide()
