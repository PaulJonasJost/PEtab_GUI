import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, \
    QObject
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QColor
import petab.v1 as petab
import tellurium as te
import libsbml
import copy

from .utils import set_dtypes, MeasurementInputDialog, ObservableInputDialog,\
    ParameterInputDialog, ConditionInputDialog, validate_value


class PandasTableModel(QAbstractTableModel):
    observable_id_changed = Signal(str, str)  # Signal to notify observableId changes

    def __init__(self, data_frame, allowed_columns, table_type, controller=None, parent=None):
        super().__init__(parent)
        self._data_frame = data_frame
        self._allowed_columns = allowed_columns
        self.table_type = table_type
        self.controller = controller
        self._invalid_cells = set()

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
        elif role == Qt.BackgroundRole and (index.row(), index.column()) in self._invalid_cells:
            return QColor(Qt.red)
        return None


    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and role == Qt.EditRole:
            column_name = self._data_frame.columns[index.column()]
            old_value = self._data_frame.iloc[index.row(), index.column()]
            if column_name == "observableId":
                self._data_frame.iloc[index.row(), index.column()] = value
                if old_value != value:
                    self.dataChanged.emit(index, index, [Qt.DisplayRole])
                    self.observable_id_changed.emit(old_value, value)
            else:
                expected_type = self._allowed_columns.get(column_name)
                if expected_type:
                    tried_value = value
                    value, error_message = validate_value(value, expected_type)
                    if error_message:
                        self.controller.log_message(
                            f"Column '{column_name}' expects a value of "
                            f"type {expected_type}, but got '{tried_value}'",
                            color="red"
                        )
                        return False
                self._data_frame.iloc[index.row(), index.column()] = value
                if old_value != value:
                    self.dataChanged.emit(index, index, [Qt.DisplayRole])
                    self.controller.unsaved_changes = True

            # Validate the row after setting data
            self.validate_changed_cell(index.row(), index.column())

            # Emit rowChanged signal if the table type is measurement
            if self.table_type == "measurement":
                self.dataChanged.emit(index, index, [Qt.DisplayRole])

            return True
        return False

    def validate_changed_cell(self, row_index, column_index):
        row_data = self._data_frame.iloc[row_index]
        row_data = set_dtypes(row_data.to_frame().T, self._allowed_columns)

        error_message = None
        try:
            self.check_petab_lint(row_data)
            for col in range(self.columnCount()):
                self._invalid_cells.discard((row_index, col))
            error_message = None
        except Exception as e:
            self.controller.log_message(
                f"PEtab linter failed at row {row_index}, column"
                f" {column_index}: {error_message}", color="red"
            )
            error_message = e

        if error_message:
            self._invalid_cells.add((row_index, column_index))
        else:
            self._invalid_cells.discard((row_index, column_index))

        self.dataChanged.emit(self.index(row_index, column_index),
                              self.index(row_index, column_index),
                              [Qt.BackgroundRole])

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
        self._data_frame.loc[new_index] = ""

        for key, value in kwargs.items():
            if key in self._data_frame.columns:
                expected_type = self._allowed_columns.get(key)
                if expected_type:
                    value, error_message = validate_value(value, expected_type)
                    if error_message:
                        error_message = f"Column '{key}' expects a value of type {expected_type}, but got '{value}'"
                        self.controller.log_message(
                            f"Input Error: {error_message}\n Abandoning row addition.",
                            color="red"
                        )
                        self.open_dialog_with_values(kwargs, key)
                        self._data_frame.drop(index=new_index, inplace=True)
                        self.layoutChanged.emit()
                        return False
                self._data_frame.loc[new_index, key] = value

        # Adding specific defaults based on the type of table
        if self.table_type == "observable":
            if "noiseFormula" in self._data_frame.columns:
                self._data_frame.loc[
                    new_index, "noiseFormula"] = f"noiseParameter1_{kwargs.get('observableId')}"
            if "observableTransformation" in self._data_frame.columns:
                self._data_frame.loc[
                    new_index, "observableTransformation"] = "lin"
            if "noiseDistribution" in self._data_frame.columns:
                self._data_frame.loc[new_index, "noiseDistribution"] = "normal"
            if "observableName" in self._data_frame.columns and "observableId" in kwargs:
                self._data_frame.loc[new_index, "observableName"] = kwargs.get(
                    "observableId")

        elif self.table_type == "parameter":
            if "parameterName" in self._data_frame.columns and "parameterId" in kwargs:
                self._data_frame.loc[new_index, "parameterName"] = kwargs.get(
                    "parameterId")
            if "parameterScale" in self._data_frame.columns:
                self._data_frame.loc[new_index, "parameterScale"] = "log10"
            if "lowerBound" in self._data_frame.columns:
                self._data_frame.loc[new_index, "lowerBound"] = 1e-08
            if "upperBound" in self._data_frame.columns:
                self._data_frame.loc[new_index, "upperBound"] = 1e3
            if "estimate" in self._data_frame.columns:
                self._data_frame.loc[new_index, "estimate"] = 1

        # Validate the entire row
        self.validate_new_row(new_index)
        self.layoutChanged.emit()
        self.controller.unsaved_changes = True
        return True

    def validate_new_row(self, row_index):
        row_data = self._data_frame.iloc[row_index]
        row_data = set_dtypes(row_data.to_frame().T, self._allowed_columns)
        error_message = None
        try:
            self.controller.check_petab_lint(row_data, self.table_type)
            error_message = None
        except Exception as e:
            error_message = e

        if error_message:
            for col in range(self.columnCount()):
                self._invalid_cells.add((row_index, col))
        else:
            for col in range(self.columnCount()):
                self._invalid_cells.discard((row_index, col))

        self.dataChanged.emit(self.index(row_index, 0),
                              self.index(row_index, self.columnCount() - 1),
                              [Qt.BackgroundRole])

    def check_petab_lint(self, row_data):
        # Implement the actual check logic based on the table type
        if self.table_type == "measurement":
            return petab.check_measurement_df(
                row_data,
                observable_df=petab.observables.get_observable_df(
                    copy.deepcopy(self.controller.models[1]._data_frame)
                ),
            )
        elif self.table_type == "observable":
            row_data = row_data.set_index("observableId")
            return petab.check_observable_df(row_data)
        elif self.table_type == "parameter":
            row_data = row_data.set_index("parameterId")
            return petab.check_parameter_df(
                row_data,
                observable_df=petab.observables.get_observable_df(
                    copy.deepcopy(self.controller.models[1]._data_frame)
                ),
                measurement_df=petab.measurements.get_measurement_df(
                    copy.deepcopy(self.controller.models[0]._data_frame)
                ),
                condition_df=petab.conditions.get_condition_df(
                    copy.deepcopy(self.controller.models[3]._data_frame)
                ),
                # TODO: add SBML model
            )
        elif self.table_type == "condition":
            row_data = row_data.set_index("conditionId")
            return petab.check_condition_df(
                row_data,
                observable_df=petab.conditions.get_condition_df(
                    copy.deepcopy(self.controller.models[3]._data_frame)
                ),
                # TODO: add SBML model
            )
        return True

    def add_column(self, column_name, default_value):
        self._data_frame[column_name] = default_value
        self.layoutChanged.emit()

    def open_dialog_with_values(self, values, error_key):
        if self.table_type == "measurement":
            dialog = MeasurementInputDialog(
                initial_values=values, error_key=error_key
            )
        elif self.table_type == "observable":
            dialog = ObservableInputDialog(values, error_key)
        elif self.table_type == "parameter":
            dialog = ParameterInputDialog(values, error_key)
        elif self.table_type == "condition":
            dialog = ConditionInputDialog(values, error_key)
        else:
            return
        dialog.exec()


class SbmlViewerModel(QObject):

    def __init__(self, sbml_model, parent=None):
        super().__init__(parent)
        self._sbml_model_original = sbml_model

        self.sbml_text = libsbml.writeSBMLToString(
            self._sbml_model_original.sbml_model.getSBMLDocument()
        )
        self.antimony_text = te.sbmlToAntimony(self.sbml_text)

    def convert_sbml_to_antimony(self):
        self.antimony_text = te.sbmlToAntimony(self.sbml_text)

    def convert_antimony_to_sbml(self):
        self.sbml_text = te.antimonyToSBML(self.antimony_text)
