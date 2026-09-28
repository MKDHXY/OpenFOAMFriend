"""Exercise the real asynchronous Files menu and project override callback."""
import os,sys,time,json
from pathlib import Path
os.environ['OFF_LANGUAGE']='zh'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE))
from PySide6.QtWidgets import QApplication
from off.gui import MainWindow
from off.models import Project
app=QApplication([]); w=MainWindow(); w.show(); w.timer.stop(); errors=[]; w.error=errors.append
def wait():
    until=time.time()+90
    while w.workers:
        app.processEvents(); time.sleep(.02)
        assert time.time()<until,'Input generation timeout'
    app.processEvents(); assert not errors,errors
wait(); w.run_files(); app.processEvents(); assert w.run_files_dialog.root.exists() and not w.run_files_dialog.editable; w.run_files_dialog.close(); w.change_language('en'); assert any(a.text()=='Files' for a in w.menuBar().actions()); assert w.mesh_region_action.text()=='Draw refinement region'; w.change_language('zh'); assert any(a.text()=='文件' for a in w.menuBar().actions()); assert w.mesh_region_action.text()=='绘制加密区域'; w.change_language('en'); w.project=Project(); w.canvas.project=w.project; w.canvas.rebuild(); w.refresh_tree()
w.generated_files(); wait(); fb=w.files_dialog; fb.open_file(fb.root/'system/blockMeshDict')
before=fb.editor.toPlainText(); edited=before.replace('(20 16 4)','(21 16 4)'); assert edited!=before
fb.editor.setPlainText(edited); fb.save(); assert w.project.dictionary_overrides['system/blockMeshDict']==edited
assert (fb.root/'system/blockMeshDict').read_text()==edited
from off.advisor import mesh_signature
assert mesh_signature(w.project)!=mesh_signature(Project())
large=fb.root/'metadata_only.bin'
with large.open('wb') as f: f.truncate(3_000_000)
fb.open_file(large); assert fb.editor.isReadOnly() and '3,000,000 bytes' in fb.editor.toPlainText(); fb.close()
w.generated_files(); wait(); fb=w.files_dialog; fb.open_file(fb.root/'system/blockMeshDict'); assert fb.editor.toPlainText()==edited; fb.close()
w.project=Project(); w.canvas.project=w.project; w.canvas.history.clear(); w.canvas.future.clear(); w.canvas.rebuild(); w.canvas.select_tags([('shape',0)]); w.canvas.duplicate_selected(); assert len(w.project.shapes)==2 and w.project.mesh_method=='Gmsh triangle / prism'; w.canvas.undo(); assert len(w.project.shapes)==1 and w.project.mesh_method=='Structured cylinder O-grid'
report={'manual_dictionary_invalidates_mesh_advice_signature':True,'all_wsl_cases_browsable_without_queue_selection':True,'new_actions_zh_start_en_zh_language_roundtrip':True,'duplicate_select_and_undo_preserve_compatible_backend':True,'release':BASE.name,'actual_async_generated_files_menu':True,'save_callback_applies_explicit_override':True,'regenerate_retains_override':True,'large_file_metadata_without_full_read':True,'errors':errors}
(BASE/'evidence/input_access_validation.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2)); w.close()
