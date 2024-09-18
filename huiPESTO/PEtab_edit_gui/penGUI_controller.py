from PySide6.QtWidgets import QInputDialog, QMessageBox, QFileDialog
import pandas as pd
import zipfile
from datetime import datetime
import tellurium as te
import libsbml
from io import BytesIO
import petab.v1 as petab
from .C import MEASUREMENT_COLUMNS, OBSERVABLE_COLUMNS, PARAMETER_COLUMNS, CONDITION_COLUMNS
from .utils import ParameterInputDialog, ObservableInputDialog, \
    MeasurementInputDialog, ObservableFormulaInputDialog, \
    ConditionInputDialog, set_dtypes
from .penGUI_model import PandasTableModel, SbmlViewerModel, FilterableTableModel
from PySide6.QtCore import Qt


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
            PandasTableModel(_data_frames[0], MEASUREMENT_COLUMNS, "measurement", self),
            PandasTableModel(_data_frames[1], OBSERVABLE_COLUMNS, "observable", self),
            PandasTableModel(_data_frames[2], PARAMETER_COLUMNS, "parameter", self),
            PandasTableModel(_data_frames[3], CONDITION_COLUMNS, "condition", self)
        ]
        self.filterable_models = [
            FilterableTableModel(self.models[0]),
            FilterableTableModel(self.models[1]),
            FilterableTableModel(self.models[2]),
            FilterableTableModel(self.models[3])
        ]
        for table_view, filterable_model in zip(
            self.view.tables, self.filterable_models
        ):
            filterable_model.setView(table_view)
        self.sbml_model = SbmlViewerModel(sbml_model=sbml_model)
        # set the text of the SBML and Antimony model
        self.view.sbml_text_edit.setPlainText(self.sbml_model.sbml_text)
        self.view.antimony_text_edit.setPlainText(self.sbml_model.antimony_text)
        self.view.controller = self
        self.setup_connections()

        self.allowed_columns = {
            0: MEASUREMENT_COLUMNS,
            1: OBSERVABLE_COLUMNS,
            2: PARAMETER_COLUMNS,
            3: CONDITION_COLUMNS
        }

    def setup_connections(self):
        for i, table_view in enumerate(self.view.tables):
            table_view.setModel(self.filterable_models[i])
            self.view.add_row_buttons[i].clicked.connect(
                lambda _, x=i: self.add_row(x))
            self.view.add_column_buttons[i].clicked.connect(
                lambda _, x=i: self.add_column(x))

        self.view.finish_button.clicked.connect(self.finish_editing)
        self.view.upload_data_matrix_button.clicked.connect(
            self.upload_data_matrix)
        self.view.reset_to_original_button.clicked.connect(
            self.reset_to_original_model)
        self.models[1].observable_id_changed.connect(
            self.handle_observable_id_change)
        self.view.tables[0].selectionModel().selectionChanged.connect(
            self.handle_selection_changed
        )
        self.models[0].dataChanged.connect(
            self.handle_data_changed)  # Connect dataChanged signal

        self.view.forward_sbml_button.clicked.connect(
            self.update_antimony_from_sbml
        )
        self.view.forward_antimony_button.clicked.connect(
            self.update_sbml_from_antimony
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
            self.log_message(
                f"An error occurred while uploading the data matrix: {str(e)}",
                color="red"
            )

    def load_data_matrix(self, file_name):
        data_matrix = pd.read_csv(file_name, delimiter='\t' if file_name.endswith('.tsv') else ',')
        if not any(col in data_matrix.columns for col in ["Time", "time", "t"]):
            self.log_message(
                "Invalid File, the file must contain a 'Time' column. "
                "Please ensure that the file contains a 'Time'",
                color="red"
                )
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
            self.log_message(
                f"Renaming observable '{old_id}' to '{new_id}' in all "
                f"measurements",
                color="green"
            )
            self.rename_observable_in_measurements(old_id, new_id)

    def rename_observable_in_measurements(self, old_id, new_id):
        measurement_model = self.models[0]
        rows = measurement_model._data_frame.shape[0]
        for row in range(rows):
            if measurement_model._data_frame.at[row, "observableId"] == old_id:
                measurement_model._data_frame.at[row, "observableId"] = new_id
        measurement_model.layoutChanged.emit()

    def delete_row(self, table_index, selected_rows=None):
        table_view = self.view.tables[table_index]
        model = self.models[table_index]
        selection_model = table_view.selectionModel()

        if selected_rows is None:
            selected_indexes = selection_model.selectedRows()
            selected_rows = [index.row() for index in selected_indexes]

        if not selected_rows:
            return

        for row in sorted(selected_rows, reverse=True):
            self.log_message(
                f"Deleted row {row} from {model.table_type} table."
                f" Data: {model._data_frame.iloc[row].to_dict()}",
                color="orange"
            )
            model._data_frame.drop(row, inplace=True)
        model._data_frame.reset_index(drop=True, inplace=True)

        model.layoutChanged.emit()

    def handle_selection_changed(self):
        self.update_plot()

    def update_plot(self):
        # breakpoint()
        selection_model = self.view.tables[0].selectionModel()
        indexes = selection_model.selectedIndexes()

        selected_points = {}
        if indexes:
            for index in indexes:
                row = index.row()
                observable_id = self.models[0]._data_frame.iloc[row][
                    "observableId"]
                if observable_id not in selected_points:
                    selected_points[observable_id] = []
                selected_points[observable_id].append({
                    "x": self.models[0]._data_frame.iloc[row]["time"],
                    "y": self.models[0]._data_frame.iloc[row]["measurement"]
                })

        measurement_data = self.models[0]._data_frame
        plot_data = {
            "all_data": [],
            "selected_points": selected_points
        }
        for observable_id in selected_points.keys():
            observable_data = measurement_data[
                measurement_data["observableId"] == observable_id]
            plot_data["all_data"].append({
                "observable_id": observable_id,
                "x": observable_data["time"].tolist(),
                "y": observable_data["measurement"].tolist()
            })

        self.view.update_visualization(plot_data)

    def handle_data_changed(self, top_left, bottom_right, roles):
        if not roles or Qt.DisplayRole in roles:
            self.update_plot()

    def update_plot_based_on_current_selection(self):
        selection_model = self.view.tables[0].selectionModel()
        indexes = selection_model.selectedIndexes()
        if indexes:
            selected_points = {}
            for index in indexes:
                row = index.row()
                observable_id = self.models[0]._data_frame.iloc[row][
                    "observableId"]
                if observable_id not in selected_points:
                    selected_points[observable_id] = []
                selected_points[observable_id].append({
                    "x": self.models[0]._data_frame.iloc[row]["time"],
                    "y": self.models[0]._data_frame.iloc[row]["measurement"]
                })
            self.update_plot(selected_points)

    # def find_text(self, text):
    #     for model in self.models:
    #         matching_cells = model._data_frame.map(
    #             lambda x: text in str(x))
    #         matching_indices = matching_cells.stack().index[
    #             matching_cells.stack()]
    #         if not matching_indices.empty:
    #             for row, col in matching_indices:
    #                 print(f"Found '{text}' in row {row}, column {col}")

    def replace_text(self, find_text, replace_text, selected_models):
        self.log_message(
            f"Replacing '{find_text}' with '{replace_text}' in selected tables",
            color="green"
        )
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
        self.log_message("Converting SBML to Antimony", color="green")
        self.sbml_model.sbml_text = self.view.sbml_text_edit.toPlainText()
        self.sbml_model.convert_sbml_to_antimony()
        self.view.antimony_text_edit.setPlainText(
            self.sbml_model.antimony_text)

    def update_sbml_from_antimony(self):
        self.log_message("Converting Antimony to SBML", color="green")
        self.sbml_model.antimony_text = self.view.antimony_text_edit.toPlainText()
        self.sbml_model.convert_antimony_to_sbml()
        self.view.sbml_text_edit.setPlainText(self.sbml_model.sbml_text)

    def reset_to_original_model(self):
        self.log_message(
            "Resetting the model to the original SBML and Antimony text",
            color="orange"
        )
        self.sbml_model.sbml_text = libsbml.writeSBMLToString(
            self.sbml_model._sbml_model_original.sbml_model.getSBMLDocument()
        )
        self.sbml_model.antimony_text = te.sbmlToAntimony(self.sbml_model.sbml_text)
        self.view.sbml_text_edit.setPlainText(self.sbml_model.sbml_text)
        self.view.antimony_text_edit.setPlainText(self.sbml_model.antimony_text)

    def check_petab_lint(self, row_data, table_type):
        if table_type == "measurement":
            observable_df = self.models[1]._data_frame
            return petab.check_measurement_df(row_data,
                                              observable_df=observable_df)
        elif table_type == "observable":
            return petab.check_observable_df(
                row_data.set_index("observableId"))
        elif table_type == "parameter":
            model = self.sbml_model
            observable_df = self.models[1]._data_frame
            measurement_df = self.models[0]._data_frame
            condition_df = self.models[3]._data_frame
            return petab.check_parameter_df(row_data.set_index("parameterId"),
                                            model=model,
                                            observable_df=observable_df,
                                            measurement_df=measurement_df,
                                            condition_df=condition_df)
        elif table_type == "condition":
            model = self.sbml_model
            observable_df = self.models[1]._data_frame
            return petab.check_condition_df(row_data.set_index("conditionId"),
                                            model=model,
                                            observable_df=observable_df)
        return True

    def log_message(self, message, color="black"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{timestamp}]\t <span style='color:{color};'" \
                       f">{message}</span>"
        self.view.logger.append(full_message)
