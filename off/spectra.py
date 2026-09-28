from pathlib import Path
import numpy as np
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

def force_dialog(case,parent):
    files=list((Path(case)/'postProcessing').rglob('*forceCoeffs*.dat'))
    if not files: files=list((Path(case)/'postProcessing').rglob('coefficient*.dat'))
    if not files: raise ValueError('No genuine force-coefficient file found.')
    data=np.loadtxt(files[0],comments='#'); t=data[:,0]; cd=data[:,2]; cl=data[:,3]
    # OpenFOAM Foundation forceCoeffs columns: Time, Cm, Cd, Cl, Cl(f), Cl(r).
    dt=float(np.median(np.diff(t))); uniform=np.allclose(np.diff(t),dt,rtol=1e-4,atol=1e-10)
    tu=np.arange(t[0],t[-1]+dt*.1,dt); values=cl if uniform else np.interp(tu,t,cl)
    n=len(values); spectrum=np.abs(np.fft.rfft(values))/n
    spectrum[1:-1 if n%2==0 else None]*=2
    frequencies=np.fft.rfftfreq(n,dt); peak=1+int(np.argmax(spectrum[1:])); p=__import__('json').loads((Path(case)/'off_project.json').read_text()); D=p.get('reference_length',0) or p['shapes'][0]['width']; U=p['velocity']; st=frequencies[peak]*D/U
    dlg=QDialog(parent); dlg.setWindowTitle('Actual lift / drag and unwindowed single-sided amplitude FFT'); dlg.resize(1000,760); layout=QVBoxLayout(dlg)
    fig=Figure(figsize=(9,6),tight_layout=True); axes=fig.subplots(2,1); axes[0].plot(t,cl,label='Cl'); axes[0].plot(t,cd,label='Cd'); axes[0].set(xlabel='Time / s',ylabel='Coefficient'); axes[0].legend(); axes[0].grid(alpha=.25)
    axes[1].plot(frequencies,spectrum); axes[1].set(xlabel='Frequency / Hz',ylabel='Single-sided amplitude'); axes[1].grid(alpha=.25)
    layout.addWidget(FigureCanvasQTAgg(fig)); text=f'Actual source: {files[0]}\nNo Hann window, no filtering, no zero padding, no mean removal. N={n}; Δt_sample={dt:g} s; Δf=1/(N Δt)={1/(n*dt):g} Hz; Nyquist=1/(2 Δt)={1/(2*dt):g} Hz.\nLargest non-DC bin: f={frequencies[peak]:g} Hz; St_L=fL/U={st:g}; L={D:g} m (project reference length; cylinder diameter when automatic). Nonuniform samples: {not uniform}; '+('linear resampling explicitly applied before FFT.' if not uniform else 'original equal-step samples used.')+'\nA short validation run cannot establish periodic shedding or a trustworthy St.'
    label=QLabel(text); label.setWordWrap(True); layout.addWidget(label); dlg.exec()
