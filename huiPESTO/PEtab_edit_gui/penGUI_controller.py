from PySide6.QtWidgets import QInputDialog, QMessageBox, QFileDialog
from PySide6.QtGui import QShortcut, QKeySequence
import pandas as pd
import zipfile
import tellurium as te
import libsbml
from io import BytesIO
from C import *
from utils import ParameterInputDialog, ObservableInputDialog, \
    MeasurementInputDialog, ObservableFormulaInputDialog, \
    ConditionInputDialog, set_dtypes, FindReplaceDialog
from penGUI_model import PandasTableModel, SbmlViewerModel


class Controller:
    def __init__(self, view, data_frames, sbml_model):
        self.view = view

        _data_frames = [
            set_dtypes(data_frames[0].fillna(""), MEASUREMENT_COLUMNS),
            set_dtypes(data_frames[1].fillna(""), OBSERVABLE_COLUMNS),
            set_dtypes(data_frames[2].fillna(""), PARAMETER_COLUMNS),
            set_dtypes(data_frames[3].fillna(""), CONDITION_COLUMNS)
        ]

        self.models = [
            PandasTableModel(_data_frames[0], MEASUREMENT_COLUMNS,
                             "measurement"),
            PandasTableModel(_data_frames[1], OBSERVABLE_COLUMNS,
                             "observable"),
            PandasTableModel(_data_frames[2], PARAMETER_COLUMNS, "parameter"),
            PandasTableModel(_data_frames[3], CONDITION_COLUMNS, "condition")
        ]
        self.sbml_model = SbmlViewerModel(sbml_model=sbml_model)
        # set the text of the SBML and Antimony model
        self.view.sbml_text_edit.setPlainText(self.sbml_model.sbml_text)
        self.view.antimony_text_edit.setPlainText(self.sbml_model.antimony_text)
        self.view.controller = self

        self.allowed_columns = {
            0: MEASUREMENT_COLUMNS,
            1: OBSERVABLE_COLUMNS,
            2: PARAMETER_COLUMNS,
            3: CONDITION_COLUMNS
        }

        self.petab_checkbox_states = {
            "measurement": False,
            "observable": False,
            "parameter": False,
            "condition": False
        }
        self.sbml_checkbox_states = {
            "sbml": False,
            "antimony": False
        }

        self.find_replace_shortcut = QShortcut(
            QKeySequence("Ctrl+R"),
            self.view
        )
        self.setup_connections()

    def setup_connections(self):
        for i, table_view in enumerate(self.view.tables):
            table_view.setModel(self.models[i])
            self.view.add_row_buttons[i].clicked.connect(lambda _, x=i: self.add_row(x))
            self.view.add_column_buttons[i].clicked.connect(lambda _, x=i: self.add_column(x))

        self.view.finish_button.clicked.connect(self.finish_editing)
        self.view.upload_data_matrix_button.clicked.connect(self.upload_data_matrix)
        self.view.reset_to_original_button.clicked.connect(self.reset_to_original_model)
        self.models[1].observable_id_changed.connect(self.handle_observable_id_change)
        self.view.tables[0].selectionModel().selectionChanged.connect(
            self.handle_selection_changed
        )

        self.view.forward_sbml_button.clicked.connect(
            self.update_antimony_from_sbml
        )
        self.view.forward_antimony_button.clicked.connect(
            self.update_sbml_from_antimony
        )
        self.find_replace_shortcut.activated.connect(
            self.open_find_replace_dialog
        )

    def upload_data_matrix(self):
        file_name, _ = QFileDialog.getOpenFileName(self.view, "Open Data Matrix", "", "CSV Files (*.csv);;TSV Files (*.tsv)")
        if file_name:
            self.process_data_matrix_file(file_name)

    def process_data_matrix_file(self, file_name):
        try:
            data_matrix = self.load_data_matrix(file_name)
            if data_matrix is None or data_matrix.empty:
                return

            condition_id = "cond1"
            self.populate_tables_from_data_matrix(data_matrix, condition_id)

        except Exception as e:
            QMessageBox.critical(self.view, "Error", f"An error occurred while processing the file: {str(e)}")

    def load_data_matrix(self, file_name):
        data_matrix = pd.read_csv(file_name, delimiter='\t' if file_name.endswith('.tsv') else ',')
        if not any(col in data_matrix.columns for col in ["Time", "time", "t"]):
            QMessageBox.warning(self.view, "Invalid File", "The file must contain a 'Time' column.")
            return None

        time_column = next(col for col in ["Time", "time", "t"] if col in data_matrix.columns)
        return data_matrix.rename(columns={time_column: "time"})

    def populate_tables_from_data_matrix(self, data_matrix, condition_id):
        for col in data_matrix.columns:
            if col != "time":
                observable_id = col
                self.ensure_observable_exists(observable_id)
                self.ensure_condition_exists(condition_id)
                self.add_measurement_rows(data_matrix, observable_id, condition_id)

    def ensure_observable_exists(self, observable_id):
        if observable_id not in self.models[1]._data_frame["observableId"].values:
            self.models[1].add_row_with_defaults(
                observableId=observable_id,
                observableFormula=observable_id
            )

    def ensure_condition_exists(self, condition_id):
        if condition_id not in self.models[3]._data_frame["conditionId"].values:
            self.models[3].add_row_with_defaults(
                conditionId=condition_id, conditionName=condition_id
            )

    def add_measurement_rows(self, data_matrix, observable_id, condition_id):
        for _, row in data_matrix.iterrows():
            self.models[0].add_row_with_defaults(
                observableId=observable_id,
                measurement=row[observable_id],
                time=row["time"],
                simulationConditionId=condition_id
            )

    def add_row(self, table_index):
        if table_index == 0:
            self.add_measurement_row()
        elif table_index == 1:
            self.add_observable_row()
        elif table_index == 2:
            self.add_parameter_row()
        elif table_index == 3:
            self.add_condition_row()
        else:
            self.models[table_index].add_row()

    def add_measurement_row(self):
        condition_ids = self.models[3]._data_frame["conditionId"].tolist()
        observable_ids = self.models[1]._data_frame["observableId"].tolist()
        dialog = MeasurementInputDialog(
            condition_ids, observable_ids, parent=self.view)
        if dialog.exec():
            observable_id, measurement, timepoints, condition_id = dialog.get_inputs()
            self.process_measurement_inputs(observable_id, measurement,
                                            timepoints, condition_id)

    def process_measurement_inputs(self, observable_id, measurement,
                                   timepoints, condition_id):
        if observable_id and measurement and timepoints:
            noise_parameters = self.copy_noise_parameters(observable_id,
                                                          condition_id)
            success = self.models[0].add_row_with_defaults(
                observableId=observable_id,
                measurement=measurement,
                time=timepoints,
                simulationConditionId=condition_id,
                noiseParameters=noise_parameters
            )
            if success:
                self.add_observable_if_missing(observable_id)
                self.add_condition_if_missing(condition_id)

    def add_observable_if_missing(self, observable_id):
        if observable_id not in self.models[1]._data_frame["observableId"].values:
            formula_dialog = ObservableFormulaInputDialog(observable_id,
                                                          self.view)
            if formula_dialog.exec():
                observable_id, observable_formula = formula_dialog.get_inputs()
                self.models[1].add_row_with_defaults(
                    observableId=observable_id,
                    observableFormula=observable_formula
                )

    def add_condition_if_missing(self, condition_id):
        if condition_id and condition_id \
                not in self.models[3]._data_frame["conditionId"].values:
            condition_columns = self.models[3]._data_frame.columns.tolist()
            condition_columns.remove("conditionName")
            if len(condition_columns) > 1:
                self.prompt_condition_details(condition_id, condition_columns)
            else:
                self.models[3].add_row_with_defaults(
                    conditionId=condition_id,
                    conditionName=condition_id
                )

    def prompt_condition_details(self, condition_id, condition_columns):
        condition_dialog = ConditionInputDialog(condition_id, condition_columns, self.view)
        if condition_dialog.exec():
            condition_inputs = condition_dialog.get_inputs()
            self.models[3].add_row_with_defaults(**condition_inputs)

    def copy_noise_parameters(self, observable_id, condition_id):
        noise_parameters = ""
        measurement_df = self.models[0]._data_frame
        matching_rows = measurement_df[measurement_df["observableId"] == observable_id]
        if not matching_rows.empty:
            if condition_id:
                preferred_row = matching_rows[matching_rows["simulationConditionId"] == condition_id]
                if not preferred_row.empty:
                    noise_parameters = preferred_row["noiseParameters"].iloc[0]
                else:
                    noise_parameters = matching_rows["noiseParameters"].iloc[0]
            else:
                noise_parameters = matching_rows["noiseParameters"].iloc[0]
        return noise_parameters

    def add_observable_row(self):
        dialog = ObservableInputDialog(parent=self.view)
        if dialog.exec():
            observable_id, observable_formula = dialog.get_inputs()
            if observable_id and observable_formula:
                self.models[1].add_row_with_defaults(
                    observableId=observable_id,
                    observableFormula=observable_formula
                )

    def add_parameter_row(self):
        dialog = ParameterInputDialog(parent=self.view)
        if dialog.exec():
            parameter_id, nominal_value = dialog.get_inputs()
            if parameter_id:
                self.models[2].add_row_with_defaults(
                    parameterId=parameter_id,
                    nominalValue=nominal_value
                )

    def add_condition_row(self):
        condition_id, ok = QInputDialog.getText(self.view, "Add Condition",
                                                "Condition ID:")
        if ok and condition_id:
            condition_columns = self.models[3]._data_frame.columns.tolist()
            condition_columns.remove("conditionName")
            if len(condition_columns) > 1:
                self.prompt_condition_details(condition_id, condition_columns)
            else:
                self.models[3].add_row_with_defaults(
                    conditionId=condition_id,
                    conditionName=condition_id
                )

    def add_column(self, table_index):
        column_name, ok = QInputDialog.getText(self.view, "Add Column", "Column name:")
        if ok and column_name:
            self.add_column_to_model(table_index, column_name)

    def add_column_to_model(self, table_index, column_name):
        allowed_columns = self.allowed_columns[table_index]
        if column_name in allowed_columns:
            column_type = allowed_columns[column_name]
            default_value = "" if column_type == "STRING" else 0
            self.models[table_index].add_column(column_name, default_value)
        else:
            QMessageBox.warning(self.view, "Invalid Column", f"The column '{column_name}' is not allowed for this table.")

    def handle_observable_id_change(self, old_id, new_id):
        reply = QMessageBox.question(
            self.view, 'Rename Observable',
            f'Do you want to rename observable "{old_id}" to "{new_id}" in all measurements?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.rename_observable_in_measurements(old_id, new_id)

    def rename_observable_in_measurements(self, old_id, new_id):
        measurement_model = self.models[0]
        rows = measurement_model._data_frame.shape[0]
        for row in range(rows):
            if measurement_model._data_frame.at[row, "observableId"] == old_id:
                measurement_model._data_frame.at[row, "observableId"] = new_id
        measurement_model.layoutChanged.emit()

    def delete_row(self, table_index):
        table_view = self.view.tables[table_index]
        model = self.models[table_index]
        selection_model = table_view.selectionModel()
        selected_indexes = selection_model.selectedRows()

        if not selected_indexes:
            return

        for index in sorted(selected_indexes):
            model._data_frame.drop(index.row(), inplace=True)
        model.layoutChanged.emit()

    def handle_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            row = indexes[0].row()
            observable_id = self.models[0]._data_frame.iloc[row]["observableId"]
            selected_point = {
                "x": self.models[0]._data_frame.iloc[row]["time"],
                "y": self.models[0]._data_frame.iloc[row]["measurement"]
            }
            self.update_plot(observable_id, selected_point)

    def update_plot(self, observable_id, selected_point):
        measurement_data = self.models[0]._data_frame
        observable_data = measurement_data[measurement_data["observableId"] == observable_id]
        plot_data = {
            "x": observable_data["time"].tolist(),
            "y": observable_data["measurement"].tolist(),
            "selected_point": selected_point
        }
        self.view.update_visualization(plot_data)

    def open_find_replace_dialog(self):
        current_tab = self.view.tabs.currentIndex()
        if current_tab == 0:
            dialog = FindReplaceDialog(
                self.view, mode="petab",
                checkbox_states=self.petab_checkbox_states
            )
        elif current_tab == 1:
            dialog = FindReplaceDialog(
                self.view, mode="sbml",
                checkbox_states=self.sbml_checkbox_states
            )
        dialog.exec()

    def replace_text(self, find_text, replace_text, selected_models):
        for index in selected_models:
            model = self.models[index]
            model._data_frame.replace(find_text, replace_text, inplace=True)
            model.layoutChanged.emit()

    def finish_editing(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self.view,
                                                   "Save Project",
                                                   "",
                                                   "Zip Files (*.zip)",
                                                   options=options)
        if file_name:
            if not file_name.endswith(".zip"):
                file_name += ".zip"

            # Create a bytes buffer to hold the zip file in memory
            buffer = BytesIO()
            with zipfile.ZipFile(buffer, 'w') as zip_file:
                # Save each data frame to a CSV file in the zip archive
                for i, model in enumerate(self.models):
                    table_name = list(self.allowed_columns.keys())[i]
                    csv_data = model._data_frame.to_csv(index=False)
                    zip_file.writestr(f"{model.table_type}.csv", csv_data)

                # Save the SBML model to a file in the zip archive
                sbml_data = self.sbml_model.sbml_text
                zip_file.writestr("model.xml", sbml_data)

            # Write the buffer contents to the file
            with open(file_name, 'wb') as f:
                f.write(buffer.getvalue())

            QMessageBox.information(
                self.view, "Save Project",
                f"Project saved successfully to {file_name}"
            )

            # Ask if the user wants to close the application
            reply = QMessageBox.question(
                self.view, "Close Application",
                "Do you want to close the application?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.view.close()

    def update_antimony_from_sbml(self):
        self.sbml_model.sbml_text = self.view.sbml_text_edit.toPlainText()
        self.sbml_model.convert_sbml_to_antimony()
        self.view.antimony_text_edit.setPlainText(
            self.sbml_model.antimony_text)

    def update_sbml_from_antimony(self):
        self.sbml_model.antimony_text = self.view.antimony_text_edit.toPlainText()
        self.sbml_model.convert_antimony_to_sbml()
        self.view.sbml_text_edit.setPlainText(self.sbml_model.sbml_text)

    def reset_to_original_model(self):
        self.sbml_model.sbml_text = libsbml.writeSBMLToString(
            self.sbml_model._sbml_model_original.sbml_model.getSBMLDocument()
        )
        self.sbml_model.antimony_text = te.sbmlToAntimony(self.sbml_model.sbml_text)
        self.view.sbml_text_edit.setPlainText(self.sbml_model.sbml_text)
        self.view.antimony_text_edit.setPlainText(self.sbml_model.antimony_text)
