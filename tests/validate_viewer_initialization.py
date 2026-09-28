"""Standalone Viewer canonical selections and real 10s case reopen regression."""
import sys,json,os
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'
BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication
from off.viewer import Viewer
app=QApplication([]); v=Viewer(); v.resize(950,650)
assert v.field.currentData()=='Mesh'
assert [v.slice.itemData(i) for i in range(v.slice.count())]==['Full volume','XY mid-slice','XZ mid-slice','YZ mid-slice']
ledger=json.loads((BASE/'evidence/eight_long_runs/ledger.json').read_text(encoding='utf-8'))
case=Path(ledger['rounds'][0]['case']); v.load(next(case.glob('*.foam')))
assert len(v.result.times)==21 and v.result.times[-1]==10
v.field.setCurrentIndex(v.field.findData('p'))
for plane in ['Full volume','XY mid-slice','XZ mid-slice','YZ mid-slice']:
    v.slice.setCurrentIndex(v.slice.findData(plane)); v.render_field()
    assert v.mapper.GetInput().GetNumberOfCells()>0
v.slice.setCurrentIndex(-1); v.render_field()
assert v.mapper.GetInput().GetNumberOfCells()==5120
v.retranslate(); assert v.slice.currentData()=='Full volume'
report={'release':BASE.name,'canonical_selection_on_construction':True,'real_case_frames':21,'end_time_s':10,'all_three_real_slice_planes':True,'empty_selection_falls_back_to_full_volume':True,'errors':[]}
(BASE/'evidence/viewer_initialization_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
v.renderer.RemoveAllViewProps(); v.widget.Finalize(); v.close(); print(report)
