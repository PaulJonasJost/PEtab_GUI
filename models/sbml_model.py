from PySide6.QtCore import QObject, Signal
import tellurium as te
import libsbml
import tempfile
from petab.v1.models.sbml_model import SbmlModel
import petab.v1 as petab


class SbmlViewerModel(QObject):
    """Model for the SBML viewer.

    Attributes
    ----------
    sbml_text: str
        The SBML text.
    antimony_text: str
        The SBML model converted to Antimony.
    """
    something_changed = Signal(bool)

    def __init__(self, sbml_model: petab.models.Model, parent=None):
        super().__init__(parent)
        self._sbml_model_original = sbml_model

        self.sbml_text = libsbml.writeSBMLToString(
            self._sbml_model_original.sbml_model.getSBMLDocument()
        )
        self.antimony_text = te.sbmlToAntimony(self.sbml_text)

    def convert_sbml_to_antimony(self):
        self.antimony_text = te.sbmlToAntimony(self.sbml_text)
        self.something_changed.emit(True)

    def convert_antimony_to_sbml(self):
        self.sbml_text = te.antimonyToSBML(self.antimony_text)
        self.something_changed.emit(True)

    def get_current_sbml_model(self):
        """Temporary write SBML to file and turn into petab.models.Model."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write(self.sbml_text)
            tmp_path = tmp.name
            sbml_model = SbmlModel.from_file(tmp_path)
        return sbml_model
