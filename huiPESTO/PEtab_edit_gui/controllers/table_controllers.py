"""Classes for the controllers of the tables in the GUI."""
from PySide6.QtWidgets import QInputDialog, QMessageBox, QFileDialog
import pandas as pd
import petab.v1 as petab
from PySide6.QtCore import Signal, QObject, QModelIndex
from pathlib import Path
from ..models.pandas_table_model import PandasTableModel
from ..views.table_view import TableViewer
from ..utils import set_dtypes


class TableController(QObject):
    """Base class for table controllers."""
    overwritten_df = Signal()  # Signal to mother controller
    def __init__(
        self,
        view: TableViewer,
        model: PandasTableModel,
        logger,
        mother_controller
    ):
        """Initialize the table controller.

        Parameters
        ----------
        view: TableViewer
            The view of the table.
        model: PandasTableModel
            The model of the table.
        logger:
            Handles all logging tasks
        mother_controller: MainController
            The main controller of the application. Needed for signal
            forwarding.
        """
        super().__init__()
        self.view = view
        self.model = model
        self.logger = logger
        self.mother_controller = mother_controller
        self.view.table_view.setModel(self.model)
        self.setup_connections()
        self.setup_connections_specific()

    def setup_connections_specific(self):
        """Will be implemented in child controllers."""
        pass

    def setup_connections(self):
        """Setup connections to the view.

        Only handles connections from within the table controllers.
        """
        # if self.view.title == "Condition Table":
        #     self.view.add_column_button.clicked.connect(
        #         self.add_column
        #     )
        self.model.cell_needs_validation.connect(
            self.validate_changed_cell
        )
        self.model.inserted_row.connect(
            self.set_index_on_new_row
        )

    def validate_changed_cell(self, row, column):
        """Validate the changed cell and whether its linting is correct."""
        row_data = self.model.get_df().iloc[row]
        index_name = self.model.get_df().index.name
        row_data = row_data.to_frame().T
        row_data.index.name = index_name
        try:
            self.check_petab_lint(row_data)
            for col in range(self.model.columnCount()):
                self.model.discard_invalid_cell(row, col)
            error_message = None
        except Exception as e:
            error_message = str(e)
            self.logger.log_message(
                f"PEtab linter failed at row {row}, column {column}: "
                f"{error_message}",
                color="red"
            )
        # Update invalid cells based on the error state
        if error_message:
            self.model.add_invalid_cell(row, column)
        else:
            self.model.discard_invalid_cell(row, column)
        self.model.notify_data_color_change(row, column)

    def upload_and_overwrite_table(self, file_path=None):
        if not file_path:
            # Open a file dialog to select the CSV or TSV file
            file_path, _ = QFileDialog.getOpenFileName(
                self.view, "Open CSV or TSV", "", "CSV/TSV Files (*.csv *.tsv)"
            )
        # just in case anything goes wrong here
        if not file_path:
            return
        # convert the file path to a Path object if it is a string
        if type(file_path) is str:
            file_path = Path(file_path)

        # Determine the file extension to choose the correct separator
        if file_path.suffix == '.csv':
            separator = ';'
        elif file_path.suffix == '.tsv':
            separator = '\t'
        else:
            self.logger.log_message(
                "Unsupported file format. Please upload a CSV or TSV file.",
                color="red"
            )
            return
        try:
            new_df = pd.read_csv(file_path, sep=separator)
        except Exception as e:
            self.view.log_message(
                f"Failed to read file: {str(e)}",
                color="red"
            )
            return

        # Overwrite the table with the new DataFrame
        self.overwrite_df(new_df)

    def overwrite_df(self, new_df: pd.DataFrame):
        # TODO: Mother controller connects to overwritten_df signal. Set df
        #  in petabProblem and unsaved changes to True
        """Overwrite the DataFrame of the model with the data from the view."""
        self.model._data_frame = new_df
        self.model.layoutChanged.emit()
        self.logger.log_message(
            f"Overwrote the {self.model.table_type} table with new data.",
            color="green"
        )
        self.overwritten_df.emit()

    def delete_row(self):
        # TODO: rework get_current_table_index and place in child controllers
        table_view = self.view.table
        selection_model = table_view.selectionModel()

        selected_indexes = selection_model.selectedIndexes()
        selected_rows = [index.row() for index in selected_indexes]
        if not selected_rows:
            return

        for row in sorted(selected_rows, reverse=True):
            self.logger.log_message(
                f"Deleted row {row} from {self.model.table_type} table."
                f" Data: {self.model.get_df().iloc[row].to_dict()}",
                color="orange"
            )
            self.model._data_frame.drop(row, inplace=True)
        self.model._data_frame.reset_index(drop=True, inplace=True)
        self.model.layoutChanged.emit()
        self.model.something_changed.emit()

    def add_column(self):
        # move to child controllers
        column_name, ok = QInputDialog.getText(
            self.view, "Add Column", "Column name:"
        )
        if ok and column_name:
            self.model.insertColumn(column_name)

    def replace_text(self, find_text, replace_text):
        self.logger.log_message(
            f"Replacing '{find_text}' with '{replace_text}' in selected tables",
            color="green"
        )
        self.model._data_frame.replace(find_text, replace_text, inplace=True)
        self.model.layoutChanged.emit()
        self.model.something_changed.emit()

    def set_index_on_new_row(self, index: QModelIndex):
        """Set the index of the model when a new row is added."""
        self.view.table_view.setCurrentIndex(index)



class MeasurementController(TableController):
    """Controller of the Measurement table."""
    def check_petab_lint(self, row_data):
        """Check a single row of the model with petablint."""
        # Can this be done more elegantly?
        observable_df = self.mother_controller.model.observable._data_frame
        return petab.check_measurement_df(
            row_data,
            observable_df=observable_df,
        )

    def rename_observable(self, old_id: str, new_id: str):
        """Rename the observables in the measurement_df.

        Triggered by changes in the original observable_df id.

        Parameters
        ----------
        old_id:
            The old observable_id, which was changed.
        new_id:
            The new observable_id.
        """
        rows = self.model.get_df().shape[0]
        for row in range(rows):
            if self.model._data_frame.at[row, "observableId"] == old_id:
                self.model._data_frame.at[row, "observableId"] = new_id
        self.model.something_changed.emit(True)
        self.model.layoutChanged.emit()

    def copy_noise_parameters(
        self,
        observable_id: str,
        condition_id: str | None = None
    ) -> str:
        """Copies noise parameter from measurements already in the table.

        Measurements of similar observables are most likely assumed to
        share a noise model. Therefore, noise parameters are copied. Prefers
        matching condition_id to copy. If not Matching condition_id,
        will copy from any matching row.

        Parameters:
        ----------
        observable_id:
            The observable_id of the new measurement.
        condition_id:
            The condition_id of the new measurement.

        Returns:
            The noise parameter that has been copied, or "" if no noise
            parameter could be copied.
        """
        measurement_df = self.model.measurement._data_frame
        matching_rows = measurement_df[measurement_df["observableId"] == observable_id]
        if matching_rows.empty:
            return ""
        if not condition_id:
            return matching_rows["noiseParameters"].iloc[0]
        preferred_row = matching_rows[matching_rows["simulationConditionId"] == condition_id]
        if not preferred_row.empty:
            return preferred_row["noiseParameters"].iloc[0]
        else:
            return matching_rows["noiseParameters"].iloc[0]

    def upload_data_matrix(self):
        """Upload a data matrix to the measurement table.

        Opens a FileDialog to select a CSV file with the data matrix.
        The data matrix is a CSV file with the following columns:
        - time: Either "Time", "time" or "t". Time points of the measurements.
        - observable_ids: Observables measured at the given timepoints.
        """
        file_name, _ = QFileDialog.getOpenFileName(
            self.view,
            "Open Data Matrix",
            "",
            "CSV Files (*.csv);;TSV Files (*.tsv)"
        )
        if file_name:
            self.process_data_matrix_file(file_name)

    def process_data_matrix_file(self, file_name):
        """Process the data matrix file.

        Upload the data matrix. Then populate the measurement table with the
        new measurements. Additionally, triggers checks for observable_ids.
        """
        try:
            data_matrix = self.load_data_matrix(file_name)
            if data_matrix is None or data_matrix.empty:
                return

            condition_id = "cond1"  # Does this need adjustment?
            self.populate_tables_from_data_matrix(data_matrix, condition_id)
            self.model.something_changed.emit()

        except Exception as e:
            self.logger.log_message(
                f"An error occurred while uploading the data matrix: {str(e)}",
                color="red"
            )

    def load_data_matrix(self, file_name):
        """Loads in the data matrix. Checks for the 'time' column."""
        data_matrix = pd.read_csv(
            file_name, delimiter='\t' if file_name.endswith('.tsv') else ','
        )
        if not any(col in data_matrix.columns for col in ["Time", "time", "t"]):
            self.logger.log_message(
                "Invalid File, the file must contain a 'Time' column. "
                "Please ensure that the file contains a 'Time'",
                color="red"
            )
            return None

        time_column = next(
            col for col in ["Time", "time", "t"] if col in data_matrix.columns
        )
        return data_matrix.rename(columns={time_column: "time"})

    def populate_tables_from_data_matrix(self, data_matrix, condition_id):
        """Populate the measurement table from the data matrix."""
        for col in data_matrix.columns:
            if col == "time":
                continue
            observable_id = col
            self.model.possibly_new_condition.emit(observable_id)
            self.model.possibly_new_observable.emit(condition_id)
            self.add_measurement_rows(
                data_matrix[["time", observable_id]],
                observable_id,
                condition_id
            )

    def add_measurement_rows(self, data_matrix, observable_id, condition_id):
        """Adds multiple rows to the measurement table."""
        # check number of rows and signal row insertion
        rows = data_matrix.shape[0]
        # get current number of rows
        current_rows = self.model.get_df().shape[0]
        self.model.insertRows(position=None, rows=rows)  # Fills the table with empty rows
        top_left = self.model.createIndex(current_rows, 0)
        for i_row, (_, row) in enumerate(data_matrix.iterrows()):
            self.model.fill_row(
                i_row + current_rows,
                data={
                    "observable_id": observable_id,
                    "time": row["time"],
                    "measurement": row[observable_id],
                    "simulationConditionId": condition_id,
                }
            )
        bottom_right = self.model.createIndex(
            x - 1 for x in self.model.get_df().shape
        )
        self.model.dataChanged.emit(top_left, bottom_right)


class ConditionController(TableController):
    """Controller of the Condition table."""
    def check_petab_lint(self, row_data):
        """Check a single row of the model with petablint."""
        observable_df = self.mother_controller.model.observable.get_df()
        sbml_model = self.mother_controller.model.sbml.get_current_sbml_model()
        return petab.check_condition_df(
            row_data,
            observable_df=observable_df,
            model=sbml_model,
        )

    def maybe_add_condition(self, condition_id):
        """Add a condition to the condition table if it does not exist yet."""
        if condition_id in self.model.get_df()["conditionId"].values:
            return
        # add a row
        self.model.insertRows(position=None, rows=1)
        self.model.fill_row(
            self.model.get_df().shape[0] - 1,
            data={"conditionId": condition_id}
        )
        self.logger.log_message(
            f"Automatically added condition '{condition_id}' to the condition "
            f"table.",
            color="green"
        )


class ObservableController(TableController):
    """Controller of the Observable table."""
    observable_2be_renamed = Signal(str, str)  # Signal to mother controller

    def setup_connections_specific(self):
        """Setup connections specific to the observable controller.

        Only handles connections from within the table controllers.
        """
        self.model.observable_id_changed.connect(
            self.maybe_rename_observable
        )

    def check_petab_lint(self, row_data):
        """Check a single row of the model with petablint."""
        return petab.check_observable_df(row_data)

    def maybe_rename_observable(self, new_id, old_id):
        """Potentially rename observable_ids in measurement_df.

        Opens a dialog to ask the user if they want to rename the observables.
        If so, emits a signal to rename the observables in the measurement_df.
        """
        reply = QMessageBox.question(
            self.view, 'Rename Observable',
            f'Do you want to rename observable "{old_id}" to "{new_id}" '
            f'in all measurements?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.logger.log_message(
                f"Renaming observable '{old_id}' to '{new_id}' in all "
                f"measurements",
                color="green"
            )
            # TODO: connect this signal with the measurement function
            self.observable_2be_renamed.emit(old_id, new_id)

    def maybe_add_observable(self, observable_id, old_id=None):
        """Add an observable to the observable table if it does not exist yet.

        Currently, `old_id` is not used.
        """
        if observable_id in self.model.get_df().index:
            return
        # add a row
        self.model.insertRows(position=None, rows=1)
        self.model.fill_row(
            self.model.get_df().shape[0] - 1,
            data={"observableId": observable_id}
        )
        self.model.cell_needs_validation.emit(
            self.model.get_df().shape[0] - 1, 0
        )
        self.logger.log_message(
            f"Automatically added observable '{observable_id}' to the "
            f"observable table.",
            color="green"
        )


class ParameterController(TableController):
    """Controller of the Parameter table."""
    def check_petab_lint(self, row_data):
        """Check a single row of the model with petablint."""
        observable_df = self.mother_controller.model.observable.get_df()
        measurement_df = self.mother_controller.model.measurement.get_df()
        condition_df = self.mother_controller.model.condition.get_df()
        sbml_model = self.mother_controller.model.sbml.get_current_sbml_model()
        return petab.check_parameter_df(
            row_data,
            observable_df=observable_df,
            measurement_df=measurement_df,
            condition_df=condition_df,
            model=sbml_model,
        )
