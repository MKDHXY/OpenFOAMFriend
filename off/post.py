"""VTK OpenFOAM reader, genuine timestep access, configurable CSV and MAT."""
from pathlib import Path
import csv
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy,numpy_to_vtk

def derived_fields(grid):
    """Cell velocity components and curl(U) in s^-1, computed from real U.

    VTK reconstructed derivatives are post-processing estimates, particularly
    at boundaries; these are not additional OpenFOAM solved fields.
    """
    data=grid.GetCellData(); velocity=data.GetArray('U')
    if velocity is None or velocity.GetNumberOfComponents()!=3: return grid
    values=vtk_to_numpy(velocity)
    for name,values_part in [('u',values[:,0]),('v',values[:,1]),('w',values[:,2]),('speed',np.linalg.norm(values,axis=1))]:
        array=numpy_to_vtk(np.ascontiguousarray(values_part),deep=True); array.SetName(name); data.AddArray(array)
    gradient=vtk.vtkGradientFilter(); gradient.SetInputData(grid); gradient.SetInputScalars(vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS,'U'); gradient.ComputeGradientOff(); gradient.ComputeVorticityOn(); gradient.SetVorticityArrayName('vorticity'); gradient.Update()
    curl=gradient.GetOutput().GetCellData().GetArray('vorticity')
    if curl is not None:
        copy=vtk.vtkDoubleArray(); copy.DeepCopy(curl); data.AddArray(copy)
        values=vtk_to_numpy(copy)
        for name,part in [('vorticity_x',values[:,0]),('vorticity_y',values[:,1]),('vorticity_z',values[:,2]),('vorticity_magnitude',np.linalg.norm(values,axis=1))]:
            array=numpy_to_vtk(np.ascontiguousarray(part),deep=True); array.SetName(name); data.AddArray(array)
    return grid

class Result:
    def __init__(self,foam):
        self.foam=Path(foam); self.reader=vtk.vtkOpenFOAMReader()
        self.reader.SetFileName(str(self.foam)); self.reader.CreateCellToPointOff(); self.reader.UpdateInformation()
        self.reader.EnableAllCellArrays(); self.reader.EnableAllPatchArrays()
        values=self.reader.GetTimeValues(); self.times=[values.GetValue(i) for i in range(values.GetNumberOfValues())] if values else [0.0]
        self.select(0)
    def select(self,index):
        self.reader.UpdateTimeStep(self.times[index]); self.reader.Update(); self.output=self.reader.GetOutput()
        self.internal=None
        it=self.output.NewIterator(); it.InitTraversal()
        while not it.IsDoneWithTraversal():
            block=it.GetCurrentDataObject()
            if isinstance(block,vtk.vtkUnstructuredGrid) and block.GetNumberOfCells(): self.internal=block; break
            it.GoToNextItem()
        if self.internal is None: raise RuntimeError('No serial internal mesh found. Reconstruct first; use .foam inside the real case.')
        derived_fields(self.internal); self.index=index; return self.internal
    def arrays(self):
        data=self.internal.GetCellData(); return [data.GetArrayName(i) for i in range(data.GetNumberOfArrays())]
    def columns(self):
        filt=vtk.vtkCellCenters(); filt.SetInputData(self.internal); filt.Update()
        xyz=vtk_to_numpy(filt.GetOutput().GetPoints().GetData())
        cols={'x':xyz[:,0],'y':xyz[:,1],'z':xyz[:,2],'t':np.full(len(xyz),self.times[self.index])}
        for name in self.arrays():
            arr=vtk_to_numpy(self.internal.GetCellData().GetArray(name))
            if arr.ndim==1: cols[name]=arr
            else:
                count=arr.shape[1]
                components=('x','y','z') if count==3 else ('xx','xy','xz','yy','yz','zz') if count==6 else ('xx','xy','xz','yx','yy','yz','zx','zy','zz') if count==9 else tuple(str(i) for i in range(count))
                for k,axis in enumerate(components): cols[name+'_'+axis]=arr[:,k]
                weights=np.array([1,2,2,1,2,1]) if count==6 else np.ones(count)
                cols[name+'_mag']=np.sqrt(np.sum(arr*arr*weights,axis=1))
        return cols
    def csv(self,path,columns,stride=1,all_times=False):
        import os,uuid
        if stride<1: raise ValueError('Row stride must be >=1')
        if not columns: raise ValueError('Select at least one CSV column.')
        old=self.index; target=Path(path); temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.partial')
        try:
            with temporary.open('w',newline='',encoding='utf-8') as f:
                writer=csv.writer(f); writer.writerow(columns)
                for i in range(len(self.times)) if all_times else [old]:
                    self.select(i); data=self.columns()
                    if any(k not in data for k in columns): raise ValueError('Unknown column; available: '+', '.join(data))
                    writer.writerows(np.column_stack([data[k] for k in columns])[::stride])
            os.replace(temporary,target)
        finally:
            self.select(old)
            if temporary.exists(): temporary.unlink()
    def mat(self,path):
        from scipy.io import savemat
        chunks=[]; full=[]; old=self.index
        for i in range(len(self.times)):
            self.select(i); c=self.columns(); chunks.append(np.column_stack([c['x'],c['y'],c['t'],c['U_x'],c['U_y'],c['p']])); full.append(np.column_stack([c['x'],c['y'],c['z'],c['t'],c['U_x'],c['U_y'],c['U_z'],c['p']]))
        savemat(path,{'xytuvp':np.vstack(chunks),'xyztuvwp':np.vstack(full),'time_values_s':np.array(self.times),'columns':np.array(['x','y','t','u','v','p'],dtype=object),'columns_3d':np.array(['x','y','z','t','u','v','w','p'],dtype=object),'units':np.array(['m','m','s','m/s','m/s','m2/s2'],dtype=object),'z_planes':np.unique(self.columns()['z']),'note':'For 3D PINNs use xyztuvwp; xytuvp omits per-row z and w.'})
        self.select(old)
