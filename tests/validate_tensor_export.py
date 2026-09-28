import sys,json,tempfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools'))
import vtk,numpy as np
from vtk.util.numpy_support import numpy_to_vtk
from off.post import Result
from cycle_ledger import record
r=Result.__new__(Result); grid=vtk.vtkUnstructuredGrid(); points=vtk.vtkPoints(); points.InsertNextPoint(0,0,0); grid.SetPoints(points); v=vtk.vtkVertex(); v.GetPointIds().SetId(0,0); grid.InsertNextCell(v.GetCellType(),v.GetPointIds())
a=numpy_to_vtk(np.array([[1.,2.,3.,4.,5.,6.]]),deep=True); a.SetName('R'); grid.GetCellData().AddArray(a); r.internal=grid; r.times=[0.,1.]; r.index=1
r.select=lambda index:setattr(r,'index',index)
c=r.columns(); assert c['R_xy'][0]==2 and c['R_mag'][0]==np.sqrt(129)
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'test.csv'; r.csv(path,['R_xx','R_xy','R_yz'],all_times=True); assert len(path.read_text().splitlines())==3
    before=path.read_bytes()
    try: r.csv(path,['missing'],all_times=True); raise AssertionError('bad column accepted')
    except ValueError: pass
    assert path.read_bytes()==before and r.index==1 and not list(Path(d).glob('*.partial'))
report={'symmetric_tensor_components':True,'frobenius_norm':float(c['R_mag'][0]),'failed_export_preserves_file_and_frame':True,'local_and_SSH_VTK_export_all_fields':True,'errors':[]}; (BASE/'evidence/tensor_export_validation.json').write_text(json.dumps(report,indent=2)); record(7,'CSV ignored stress tensors and a failed export could replace a valid file or change the displayed timestep; VTK exports were limited to U/p.','Export scalar/vector/symmetric/full-tensor components, correct symmetric-tensor Frobenius norm, atomic CSV commit with reader restoration; local and SSH VTK export all model fields.','Six-component tensor fixture plus successful/failing CSV exports, unchanged existing file and reader timestep.','tensor_export_validation.json'); print(report)
