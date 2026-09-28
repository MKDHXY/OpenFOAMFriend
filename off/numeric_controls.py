"""Scientific numeric display with Qt's native spin-box keyboard/step contract."""
import math
from PySide6.QtWidgets import QDoubleSpinBox,QAbstractSpinBox
from PySide6.QtGui import QDoubleValidator,QValidator
class ScientificSpin(QDoubleSpinBox):
    def __init__(self,*args):
        super().__init__(*args); self.setDecimals(16); self.setStepType(QAbstractSpinBox.AdaptiveDecimalStepType)
    def textFromValue(self,value): return format(value,'.12g')
    def valueFromText(self,text):
        try: return float(text.strip())
        except ValueError: return self.value()
    def validate(self,text,position):
        if not hasattr(self,'_validator'): self._validator=QDoubleValidator(self)
        validator=self._validator; validator.setRange(self.minimum(),self.maximum(),16); validator.setNotation(QDoubleValidator.ScientificNotation)
        state,body,pos=validator.validate(text,position)
        try:
            if not math.isfinite(float(text)): state=QValidator.Invalid
        except ValueError: pass
        return state,body,pos
