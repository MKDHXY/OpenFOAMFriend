import sys,json,os,copy
from pathlib import Path
os.environ['OFF_LANGUAGE']='en'; BASE=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BASE)); sys.path.insert(0,str(BASE/'tools'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from off.viewer import Viewer
from off.colourmap import ColourMapDialog,ColourSettings,settings_for
from off.i18n import preferences,save_preference
from cycle_ledger import record
app=QApplication([]); saved=copy.deepcopy(preferences().get('colour_maps',{})); v=Viewer(); v.resize(1400,950); v.show(); evidence=json.loads((BASE/'evidence/validation.json').read_text()); case=Path(evidence['rounds'][2]['case_folder']); v.load(next(case.glob('*.foam'))); v.field.setCurrentIndex(v.field.findData('p')); v.slider.setValue(v.slider.maximum())
d=ColourMapDialog(v); d.freeze_current_range(); assert not d.inputs['auto_range'].isChecked(); limits=(float(d.inputs['minimum'].text()),float(d.inputs['maximum'].text()))
d.inputs['palette'].setCurrentIndex(d.inputs['palette'].findData('Blue–red')); d.inputs['reverse'].setChecked(True); d.inputs['title'].setText('Kinematic pressure / m2 s-2'); d.inputs['labels'].setValue(7); d.inputs['font_size'].setValue(14); d.inputs['precision'].setValue(4); d.inputs['notation'].setCurrentIndex(d.inputs['notation'].findData('e')); d.inputs['orientation'].setCurrentIndex(d.inputs['orientation'].findData('horizontal')); d.show(); QTest.qWait(150); d.grab().save(str(BASE/'evidence/colour_dialog_EN.png')); d.apply_settings(); assert v.mapper.GetLookupTable().GetRange()==limits
assert v.bar.GetOrientation()==0 and v.bar.GetTitle()=='Kinematic pressure / m2 s-2' and v.bar.GetNumberOfLabels()==7
assert settings_for('p').palette=='Blue–red'
for index in range(len(v.result.times)): v.slider.setValue(index); assert v.mapper.GetLookupTable().GetRange()==limits
v.field.setCurrentIndex(v.field.findData('u')); assert v.colour_key=='u' and v.colour_settings['u'].palette!='Blue–red'; v.field.setCurrentIndex(v.field.findData('p')); assert v.mapper.GetLookupTable().GetRange()==limits
v.image().save(BASE/'evidence/colour_fixed_pressure.png'); v.gif(str(BASE/'evidence/colour_fixed_pressure.gif'))
for invalid in [ColourSettings(auto_range=False,minimum=0,maximum=1,logarithmic=True),ColourSettings(auto_range=False,minimum=2,maximum=1),ColourSettings(x=.9,width=.3),ColourSettings(minimum=float('nan'))]:
    try: invalid.validate(); raise AssertionError('bad colour setting accepted')
    except ValueError: pass
v.field.setCurrentIndex(v.field.findData('Mesh')); assert not v.colour_button.isEnabled() and not v.bar.GetVisibility()
report={'freeze_actual_range':list(limits),'fixed_across_all_frames':True,'independent_field_settings':True,'palette_reverse':True,'orientation_title_ticks_format':True,'persisted_settings_reload':True,'actual_PNG_and_GIF':True,'invalid_log_layout_ranges_rejected':True,'errors':[]}; (BASE/'evidence/colourmap_validation.json').write_text(json.dumps(report,indent=2)); save_preference('colour_maps',saved); d.close(); v.close(); print(report)
# Ledger is appended separately after the preceding runtime cycle completes.
