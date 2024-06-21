import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, QObject
from PySide6.QtGui import QColor
import petab
import tellurium as te
import libsbml

from utils import set_dtypes


class PandasTableModel(QAbstractTableModel):
    observable_id_changed = Signal(str, str)  # Signal to notify observableId changes

    def __init__(self, data_frame, allowed_columns, table_type, parent=None):
        super().__init__(parent)
        self._data_frame = data_frame
        self._allowed_columns = allowed_columns
        self.table_type = table_type
        self._invalid_rows = set()

    def sort(self, column, order):
        """
        Sort the data frame by the given column index.
        """
        column_name = self._data_frame.columns[column]
        self.layoutAboutToBeChanged.emit()
        self._data_frame.sort_values(by=column_name,
                                     ascending=(order == Qt.AscendingOrder),
                                     inplace=True)
        self._data_frame.reset_index(drop=True, inplace=True)
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return self._data_frame.shape[0]

    def columnCount(self, parent=QModelIndex()):
        return self._data_frame.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole or role == Qt.EditRole:
            value = self._data_frame.iloc[index.row(), index.column()]
            return str(value)
        elif role == Qt.BackgroundRole and index.row() in self._invalid_rows:
            return QColor(Qt.red)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and role == Qt.EditRole:
            column_name = self._data_frame.columns[index.column()]
            if column_name == "observableId":
                old_value = self._data_frame.iloc[index.row(), index.column()]
                self._data_frame.iloc[index.row(), index.column()] = value
                self.dataChanged.emit(index, index, [Qt.DisplayRole])
                if old_value != value:
                    self.observable_id_changed.emit(old_value, value)
            else:
                expected_type = self._allowed_columns.get(column_name)
                if expected_type:
                    try:
                        if expected_type == "STRING":
                            value = str(value)
                        elif expected_type == "NUMERIC":
                            value = float(value)
                        elif expected_type == "BOOLEAN":
                            value = bool(value)
                    except ValueError:
                        return False
                self._data_frame.iloc[index.row(), index.column()] = value
                self.dataChanged.emit(index, index, [Qt.DisplayRole])

            # Perform plausibility check on the row
            row_data = self._data_frame.iloc[index.row()]
            row_data = set_dtypes(row_data.to_frame().T, self._allowed_columns)
            error_message = None
            try:
                self.check_petab_lint(row_data)
            except Exception as e:
                error_message = e
            if error_message:
                self._invalid_rows.add(index.row())
            else:
                self._invalid_rows.discard(index.row())
            self.dataChanged.emit(index, index, [Qt.BackgroundRole])

            # Emit rowChanged signal if the table type is measurement
            if self.table_type == "measurement":
                self.rowChanged.emit(index.row())

            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data_frame.columns[section])
            elif orientation == Qt.Vertical:
                return str(self._data_frame.index[section])
        return None

    def add_row(self):
        new_index = len(self._data_frame)
        self._data_frame.loc[new_index] = ["" for _ in range(self._data_frame.shape[1])]
        self.layoutChanged.emit()

    def add_row_with_defaults(self, **kwargs):
        new_index = len(self._data_frame)
        if self.table_type == "observable":
            new_index = kwargs.get("observableId")
        if self.table_type == "parameter":
            new_index = kwargs.get("parameterId")
        if self.table_type == "condition":
            new_index = kwargs.get("conditionId")
        if new_index in self._data_frame.index:
            return
        self._data_frame.loc[new_index] = ""

        for key, value in kwargs.items():
            if key in self._data_frame.columns:
                # TODO: typechecks
                self._data_frame.loc[new_index, key] = value

        # Adding specific defaults based on the type of table
        if self.table_type == "measurement":
            if "noiseFormula" in self._data_frame.columns:
                self._data_frame.loc[new_index, "noiseFormula"] = f"noiseParameter1_{kwargs.get('observableId')}"
            if "observableTransformation" in self._data_frame.columns:
                self._data_frame.loc[new_index, "observableTransformation"] = "lin"
            if "noiseDistribution" in self._data_frame.columns:
                self._data_frame.loc[new_index, "noiseDistribution"] = "normal"
            if "observableName" in self._data_frame.columns and "observableId" in kwargs:
                self._data_frame.loc[new_index, "observableName"] = kwargs.get("observableId")

        elif self.table_type == "parameter":
            if "parameterName" in self._data_frame.columns and "parameterId" in kwargs:
                self._data_frame.loc[new_index, "parameterName"] = kwargs.get("parameterId")
            if "parameterScale" in self._data_frame.columns:
                self._data_frame.loc[new_index, "parameterScale"] = "log10"
            if "lowerBound" in self._data_frame.columns:
                self._data_frame.loc[new_index, "lowerBound"] = 1e-08
            if "upperBound" in self._data_frame.columns:
                self._data_frame.loc[new_index, "upperBound"] = 1e3
            if "estimate" in self._data_frame.columns:
                self._data_frame.loc[new_index, "estimate"] = 1

        self.layoutChanged.emit()

    def check_petab_lint(self, row_data):
        # Implement the actual check logic based on the table type
        if self.table_type == "measurement":
            return petab.check_measurement_df(row_data)
        elif self.table_type == "observable":
            row_data = row_data.set_index("observableId")
            return petab.check_observable_df(row_data)
        elif self.table_type == "parameter":
            row_data = row_data.set_index("parameterId")
            return petab.check_parameter_df(row_data)
        elif self.table_type == "condition":
            row_data = row_data.set_index("conditionId")
            return petab.check_condition_df(row_data)
        return True

    def add_column(self, column_name, default_value):
        self._data_frame[column_name] = default_value
        self.layoutChanged.emit()


class SbmlViewerModel(QObject):
    sbml_updated = Signal(str)
    antimony_updated = Signal(str)

    def __init__(self, sbml_model, parent=None):
        super().__init__(parent)
        self._sbml_model = sbml_model

        self._sbml_text = libsbml.writeSBMLToString(self._sbml_model.sbml_model.getSBMLDocument())
        self._antimony_text = te.sbmlToAntimony(self._sbml_text)

    @property
    def sbml_text(self):
        return self._sbml_text

    @sbml_text.setter
    def sbml_text(self, value):
        if value != self._sbml_text:
            self._sbml_text = value
            self.convert_sbml_to_antimony()
            self.sbml_updated.emit(self._sbml_text)

    @property
    def antimony_text(self):
        return self._antimony_text

    @antimony_text.setter
    def antimony_text(self, value):
        if value != self._antimony_text:
            self._antimony_text = value
            self.convert_antimony_to_sbml()
            self.antimony_updated.emit(self._antimony_text)

    def convert_sbml_to_antimony(self):
        # Implement the actual conversion logic here
        self._antimony_text = f"Converted Antimony from SBML: {self._sbml_text}"

    def convert_antimony_to_sbml(self):
        # Implement the actual conversion logic here
        self._sbml_text = f"Converted SBML from Antimony: {self._antimony_text}"