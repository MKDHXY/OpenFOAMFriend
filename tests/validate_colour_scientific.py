import sys,json,os
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools'))
import vtk
from PySide6.QtWidgets import QApplication
from off.colourmap import ColourSettings,ColourMapDialog,apply_lookup
from off.viewer import Viewer
from cycle_ledger import record
app=QApplication([]); v=Viewer(); v.colour_key='pressure_test'; v.colour_range=(-1e-14,3e-14)
d=ColourMapDialog(v); d.inputs['auto_range'].setChecked(False); d.inputs['minimum'].setText('-1e-14'); d.inputs['maximum'].setText('3e-14')
s=d.values(); assert s.minimum==-1e-14 and s.maximum==3e-14
mapper=vtk.vtkDataSetMapper(); bar=vtk.vtkScalarBarActor(); assert apply_lookup(mapper,bar,s,v.colour_range,'p')==(-1e-14,3e-14)
assert mapper.GetLookupTable().GetRange()==(-1e-14,3e-14)
report={'scientific_limits_preserved':True,'actual_vtk_range':list(mapper.GetLookupTable().GetRange()),'errors':[]}; (BASE/'evidence/colour_scientific_validation.json').write_text(json.dumps(report,indent=2))
record(2,'Fixed-decimal spin boxes rounded small scientific colour limits to zero.','Scientific-notation inputs preserve finite small/large scalar limits without fixed decimal rounding.','Enter -1e-14 and 3e-14 in actual colour dialog and verify VTK lookup range.','colour_scientific_validation.json')
d.close(); v.close(); print(report)
