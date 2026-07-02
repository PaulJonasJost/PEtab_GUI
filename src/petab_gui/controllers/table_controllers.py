"""Classes for the controllers of the tables in the GUI."""

import logging
import re
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
import petab.v1 as petab
from PySide6.QtCore import QModelIndex, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from ..C import COLUMN, INDEX
from ..commands import RenameValueCommand
from ..models.pandas_table_model import (
    PandasTableFilterProxy,
    PandasTableModel,
)
from ..resources.whats_this import WHATS_THIS
from ..settings_manager import settings_manager
from ..utils import (
    CaptureLogHandler,
    get_selected,
    process_file,
)
from ..views.dialogs import ConditionInputDialog, DoseTimeDialog
from ..views.table_view import (
    ColumnSuggestionDelegate,
    ComboBoxDelegate,
    ParameterIdSuggestionDelegate,
    SingleSuggestionDelegate,
    TableViewer,
)
from .utils import linter_wrapper, prompt_overwrite_or_append, save_petab_table


class TableController(QObject):
    """Base class for table controllers."""

    overwritten_df = Signal()  # Signal to mother controller

    def __init__(
        self,
        view: TableViewer,
        model: PandasTableModel,
        logger,
        undo_stack,
        mother_controller,
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
        self.model.view = self.view.table_view
        self.proxy_model = PandasTableFilterProxy(model)
        self.logger = logger
        self.undo_stack = undo_stack
        self.model.undo_stack = undo_stack
        self.check_petab_lint_mode = True
        if model.table_type in ["simulation", "visualization"]:
            self.check_petab_lint_mode = False
        self.mother_controller = mother_controller
        self.view.table_view.setModel(self.proxy_model)
        self.view.table_view.setWhatsThis(
            WHATS_THIS["tables"][model.table_type]["table"]
        )
        self.setup_connections()
        self.setup_connections_specific()

        self.completers = {}
        self.setup_completers()

    def setup_completers(self):
        pass

    def release_completers(self):
        """Sets the completers to None. Safety Measure."""
        if not self.completers:
            return
        for column_index in range(self.model.columnCount()):
            self.view.table_view.setItemDelegateForColumn(column_index, None)
        self.completers = {}

    def setup_connections_specific(self):
        """Will be implemented in child controllers."""
        pass

    def setup_connections(self):
        """Setup connections to the view.

        Only handles connections from within the table controllers.
        """
        self.model.new_log_message.connect(self.logger.log_message)
        self.model.cell_needs_validation.connect(self.validate_changed_cell)
        self.model.inserted_row.connect(self.set_index_on_new_row)
        settings_manager.settings_changed.connect(self.update_defaults)

    def setup_context_menu(self, actions):
        """Setup context menus for this table.

        Sets up both the table body context menu and the header context menus
        using the same actions dictionary for consistency.

        Args:
            actions: Dictionary of QAction objects
        """
        view = self.view.table_view
        view.setup_context_menu(actions)
        view.setup_header_context_menus(actions)

    def validate_changed_cell(self, row, column):
        """Validate the changed cell and whether its linting is correct."""
        if not self.check_petab_lint_mode:
            return
        df = self.model.get_df()
        row_data = df.iloc[row]
        index_name = df.index.name
        row_data = row_data.to_frame().T
        row_data.index.name = index_name
        row_name = row_data.index[0]
        if column == 0 and self.model._has_named_index:
            col_name = index_name
        else:
            col_name = df.columns[column - self.model.column_offset]
        is_valid = self.check_petab_lint(row_data, row_name, col_name)
        if is_valid:
            for col in range(self.model.columnCount()):
                self.model.discard_invalid_cell(row, col)
        else:
            self.model.add_invalid_cell(row, column)
        self.model.notify_data_color_change(row, column)

    def open_table(self, file_path=None, separator=None, mode="overwrite"):
        if not file_path:
            # Open a file dialog to select the CSV or TSV file
            file_path, _ = QFileDialog.getOpenFileName(
                self.view,
                "Open CSV or TSV",
                "",
                "CSV/TSV/TXT Files (*.csv *.tsv *.txt)",
            )
        # just in case anything goes wrong here
        if not file_path:
            return
        # convert the file path to a Path object if it is a string
        if type(file_path) is str:
            file_path = Path(file_path)

        if separator is None:
            actionable, separator = process_file(file_path, self.logger)
            if actionable in ["yaml", "sbml", "data_matrix", None]:  # no table
                return
        try:
            if self.model.table_type in [
                "measurement",
                "visualization",
                "simulation",
            ]:
                new_df = pd.read_csv(file_path, sep=separator)
            else:
                new_df = pd.read_csv(file_path, sep=separator, index_col=0)
        except Exception as e:
            self.logger.log_message(
                f"Failed to read file: {str(e)}", color="red"
            )
            return
        dtypes = {
            col: self.model._allowed_columns.get(col, {"type": np.object_})[
                "type"
            ]
            for col in new_df.columns
        }
        new_df = new_df.astype(dtypes)
        if mode is None:
            mode = prompt_overwrite_or_append(self)
        # Overwrite or append the table with the new DataFrame
        if mode == "append":
            self.append_df(new_df)
        elif mode == "overwrite":
            self.overwrite_df(new_df)
            self.model.reset_invalid_cells()

    def overwrite_df(self, new_df: pd.DataFrame):
        """Overwrite the DataFrame of the model with the data from the view."""
        self.proxy_model.setSourceModel(None)
        self.model.beginResetModel()
        self.model._data_frame = new_df
        self.model.endResetModel()
        self.logger.log_message(
            f"Overwrote the {self.model.table_type} table with new data.",
            color="green",
        )
        # test: overwrite the new model as source model
        self.proxy_model.setSourceModel(self.model)
        # change default sizing
        self.view.table_view.reset_column_sizes()
        self.overwritten_df.emit()

    def append_df(self, new_df: pd.DataFrame):
        """Append the DataFrame of the model with the data from the view.

        Merges two DataFrames:
            1. Columns are the union of both DataFrame columns.
            2. Rows are the union of both DataFrame rows (duplicates removed)
        """
        self.proxy_model.setSourceModel(None)
        self.model.beginResetModel()
        current_df = self.model.get_df()

        # For tables without a named index (measurement, visualization,
        # simulation), ignore the index to avoid removing appended data due
        # to index conflicts
        if self.model.table_type in [
            "measurement",
            "visualization",
            "simulation",
        ]:
            combined_df = pd.concat(
                [current_df, new_df], axis=0, ignore_index=True
            )
        else:
            # For tables with named indices, concatenate and remove
            # duplicate indices
            combined_df = pd.concat([current_df, new_df], axis=0)
            combined_df = combined_df[
                ~combined_df.index.duplicated(keep="first")
            ]

        self.model._data_frame = combined_df
        self.model.endResetModel()
        self.logger.log_message(
            f"Appended the {self.model.table_type} table with new data.",
            color="green",
        )
        self.proxy_model.setSourceModel(self.model)
        self.overwritten_df.emit()

    def clear_table(self):
        """Clear the table."""
        self.model.clear_table()

    def delete_row(self):
        """Delete the selected row(s) from the table."""
        table_view = self.view.table_view

        selected_rows = get_selected(table_view)
        if not selected_rows:
            return
        self.model.update_invalid_cells(selected_rows, mode="rows")
        for row in sorted(selected_rows, reverse=True):
            if row >= self.model.rowCount() - 1:
                continue
            row_info = self.model.repository.get_row(row)
            self.model.delete_row(row)
            self.logger.log_message(
                f"Deleted row {row} from {self.model.table_type} table."
                f" Data: {row_info}",
                color="orange",
            )
        self.model.something_changed.emit(True)

    def add_row(self):
        """Add a row to the datatable."""
        row_count = self.model.rowCount() - 1
        if self.model.insertRows(row_count, 1):
            new_row_index = self.model.index(row_count, 0)

            selection_model = self.view.table_view.selectionModel()
            if selection_model:
                selection_model.select(
                    new_row_index, selection_model.SelectionFlag.ClearAndSelect
                )
            self.view.table_view.scrollTo(new_row_index)
            self.view.table_view.setCurrentIndex(new_row_index)

    def delete_column(self):
        """Delete the selected column(s) from the table."""
        table_view = self.view.table_view

        selected_columns = get_selected(table_view, mode=COLUMN)
        if not selected_columns:
            return
        deleted_columns = set()
        for column in sorted(selected_columns, reverse=True):
            # safely delete potential item delegates
            allow_del, column_name = self.model.allow_column_deletion(column)
            if not allow_del:
                self.logger.log_message(
                    f"Cannot delete column {column_name}, as it is a "
                    f"required column!",
                    color="red",
                )
                continue
            if column_name in self.completers:
                self.view.table_view.setItemDelegateForColumn(column, None)
                del self.completers[column_name]
            self.model.delete_column(column)
            self.logger.log_message(
                f"Deleted column '{column_name}' from "
                f"{self.model.table_type} table.",
                color="orange",
            )
            deleted_columns.add(column)
        self.model.update_invalid_cells(deleted_columns, mode="columns")
        self.model.something_changed.emit(True)

    def add_column(self, column_name: str = None):
        """Add a column to the datatable."""
        if not column_name:
            column_name, ok = QInputDialog.getText(
                self.view, "Add Column", "Enter the name of the new column:"
            )
            if not ok:
                return
        self.model.insertColumn(column_name)

    def clear_cells(self):
        """Clear all selected cells."""
        selected = get_selected(self.view.table_view, mode=INDEX)
        self.model.clear_cells(selected)

    def set_index_on_new_row(self, index: QModelIndex):
        """Set the index of the model when a new row is added."""
        proxy_index = self.proxy_model.mapFromSource(index)
        self.view.table_view.setCurrentIndex(proxy_index)

    def filter_table(self, text):
        """Filter the table."""
        self.proxy_model.setFilterRegularExpression(text)
        self.proxy_model.setFilterKeyColumn(-1)

    def remove_filter(self):
        """Remove the filter from the table."""
        self.proxy_model.setFilterRegularExpression("")
        self.proxy_model.setFilterKeyColumn(-1)

    def copy_to_clipboard(self):
        """Copy the currently selected cells to the clipboard."""
        self.view.copy_to_clipboard()

    def paste_from_clipboard(self):
        """Paste the clipboard content to the currently selected cells."""
        old_lint = self.check_petab_lint_mode
        self.check_petab_lint_mode = False
        self.view.paste_from_clipboard()
        self.check_petab_lint_mode = old_lint
        try:
            self.check_petab_lint()
        except Exception as e:
            self.logger.log_message(
                f"PEtab linter failed after copying: {str(e)}", color="red"
            )

    def check_petab_lint(
        self,
        row_data: pd.DataFrame = None,
        row_name: str = None,
        col_name: str = None,
    ):
        """Check a single row of the model with petablint."""
        raise NotImplementedError(
            "This method must be implemented in child classes."
        )

    def find_text(
        self, text, case_sensitive=False, regex=False, whole_cell=False
    ):
        """Efficiently find all matching cells."""
        df = self.model.get_df()

        # Search in the main DataFrame
        if regex:
            pattern = re.compile(text, 0 if case_sensitive else re.IGNORECASE)
            mask = df.map(
                lambda cell: bool(pattern.fullmatch(str(cell)))
                if whole_cell
                else bool(pattern.search(str(cell)))
            )
        else:
            text = text.lower() if not case_sensitive else text
            mask = (
                df.map(
                    lambda cell: text == str(cell).lower()
                    if whole_cell
                    else text in str(cell).lower()
                )
                if not case_sensitive
                else df.map(
                    lambda cell: text == str(cell)
                    if whole_cell
                    else text in str(cell)
                )
            )

        # Find matches
        match_indices = list(zip(*mask.to_numpy().nonzero(), strict=False))
        table_matches = [
            (row, col + self.model.column_offset) for row, col in match_indices
        ]

        # Search in the index if it's named
        index_matches = []
        if isinstance(df.index, pd.Index) and df.index.name:
            if regex:
                index_mask = df.index.to_series().map(
                    lambda idx: bool(pattern.fullmatch(str(idx)))
                    if whole_cell
                    else bool(pattern.search(str(idx)))
                )
            else:
                index_mask = (
                    df.index.to_series().map(
                        lambda idx: text == str(idx).lower()
                        if whole_cell
                        else text in str(idx).lower()
                    )
                    if not case_sensitive
                    else df.index.to_series().map(
                        lambda idx: text == str(idx)
                        if whole_cell
                        else text in str(idx)
                    )
                )

            index_matches = [
                (df.index.get_loc(idx), 0)
                for idx in index_mask[index_mask].index
            ]

        all_matches = index_matches + table_matches

        # 🔹 Highlight matched text
        self.highlight_text(all_matches)
        return all_matches

    def highlight_text(self, matches):
        """Color the text of all matched cells in yellow."""
        self.model.highlighted_cells = set(matches)
        top_left = self.model.index(0, 0)
        bottom_right = self.model.index(
            self.model.rowCount() - 1, self.model.columnCount() - 1
        )
        self.model.dataChanged.emit(
            top_left, bottom_right, [Qt.ForegroundRole]
        )

    def cleanse_highlighted_cells(self):
        """Cleanses the highlighted cells."""
        self.model.highlighted_cells = set()
        top_left = self.model.index(0, 0)
        bottom_right = self.model.index(
            self.model.rowCount() - 1, self.model.columnCount() - 1
        )
        self.model.dataChanged.emit(
            top_left, bottom_right, [Qt.ForegroundRole]
        )

    def focus_match(self, match, with_focus: bool = False):
        """Focus and select the given match in the table."""
        if match is None:
            self.view.table_view.clearSelection()
            return
        row, col = match
        index = self.model.index(row, col)
        if not index.isValid():
            return
        proxy_index = self.view.table_view.model().mapFromSource(index)
        if not proxy_index.isValid():
            return

        self.view.table_view.setCurrentIndex(proxy_index)
        self.view.table_view.scrollTo(
            proxy_index, QAbstractItemView.EnsureVisible
        )
        if with_focus:
            self.view.table_view.setFocus()

    def replace_text(
        self, row, col, replace_text, search_text, case_sensitive, regex
    ):
        """Replace the text in the given cell and update highlights."""
        index = self.model.index(row, col)
        original_text = self.model.data(index, Qt.DisplayRole)

        if not original_text:
            return

        if regex:
            pattern = re.compile(
                search_text, 0 if case_sensitive else re.IGNORECASE
            )
            new_text = pattern.sub(replace_text, original_text)
        else:
            if not case_sensitive:
                search_text = re.escape(search_text.lower())
                new_text = re.sub(
                    search_text,
                    replace_text,
                    original_text,
                    flags=re.IGNORECASE,
                )
            else:
                new_text = original_text.replace(search_text, replace_text)

        if new_text != original_text:
            self.model.setData(index, new_text, Qt.EditRole)
            self.model.highlighted_cells.discard((row, col))
            self.model.dataChanged.emit(index, index, [Qt.DisplayRole])

    @staticmethod
    def _find_and_replace_in_text(
        text: str,
        search: str,
        replace: str,
        case_sensitive: bool,
        use_regex: bool,
    ) -> tuple[bool, str]:
        """Find and replace text with given options.

        Args:
            text: The text to search in
            search: The search pattern
            replace: The replacement text
            case_sensitive: Whether to match case
            use_regex: Whether to use regex matching

        Returns:
            Tuple of (matched, new_text) where matched indicates if
            replacement occurred
        """
        if use_regex:
            pattern = re.compile(
                search, 0 if case_sensitive else re.IGNORECASE
            )
            new_text = pattern.sub(replace, text)
            return new_text != text, new_text

        # Non-regex replacement
        if case_sensitive:
            matched = search in text
            new_text = text.replace(search, replace) if matched else text
        else:
            matched = search.lower() in text.lower()
            new_text = (
                re.sub(re.escape(search), replace, text, flags=re.IGNORECASE)
                if matched
                else text
            )

        return matched, new_text

    def replace_all(
        self, search_text, replace_text, case_sensitive=False, regex=False
    ):
        """Replace all occurrences of search term in Model with undo.

        Replace all occurrences of the search term in the Model with undo
        support.
        """
        if not search_text or not replace_text:
            return

        from ..commands import ModifyDataFrameCommand

        # Find all matching cells using repository
        matches = self.model.repository.find_cells(
            search_text, regex=regex, case_sensitive=case_sensitive
        )

        # Process all matches in a single pass
        changes = {}  # {(row_id, col_name): (old_val, new_val)}
        index_renames = []  # [(old_id, new_id, row_idx)]

        for row_idx, col_name, old_val in matches:
            if col_name == "_index_":
                # Handle index matches
                if self.model._has_named_index:
                    matched, new_str = self._find_and_replace_in_text(
                        str(old_val),
                        search_text,
                        replace_text,
                        case_sensitive,
                        regex,
                    )
                    if matched and new_str != str(old_val):
                        index_renames.append((old_val, new_str, row_idx))
            else:
                # Handle cell matches
                if not pd.isna(old_val):
                    matched, new_str = self._find_and_replace_in_text(
                        str(old_val),
                        search_text,
                        replace_text,
                        case_sensitive,
                        regex,
                    )
                    if matched and new_str != str(old_val):
                        row_id = self.model.repository.get_row_id(row_idx)
                        changes[(row_id, col_name)] = (old_val, new_str)

        # Create undo command(s)
        if changes or index_renames:
            if self.model.undo_stack:
                # Use macro to group cell changes + index renames into
                # one undo operation
                self.model.undo_stack.beginMacro(
                    f"Replace '{search_text}' with '{replace_text}'"
                )

                # Push cell changes command
                if changes:
                    command = ModifyDataFrameCommand(
                        self.model, changes, "Replace in cells"
                    )
                    self.model.undo_stack.push(command)

                # Push index rename commands
                if index_renames:
                    from ..commands import RenameIndexCommand

                    for old_id, new_id, row_idx in index_renames:
                        model_index = self.model.index(row_idx, 0)
                        cmd = RenameIndexCommand(
                            self.model, old_id, new_id, model_index
                        )
                        self.model.undo_stack.push(cmd)

                self.model.undo_stack.endMacro()
            else:
                # Fallback: apply changes directly if no undo stack
                for (row_id, col_name), (_old_val, new_val) in changes.items():
                    row_pos = self.model.repository.get_row_position(row_id)
                    self.model.repository.set_cell(row_pos, col_name, new_val)
                for old_id, new_id, _ in index_renames:
                    self.model.repository.rename_index(old_id, new_id)

    def get_columns(self):
        """Get the columns of the table."""
        df = self.model.get_df()
        # if it is a named index, add it to the columns
        if df.index.name:
            return [df.index.name] + df.columns.tolist()
        return df.columns.tolist()

    def update_defaults(self, settings_changed):
        """Update the default values of the model."""
        # if the signal is not "table_defaults/table_name" return
        if not settings_changed.startswith("table_defaults"):
            return
        table_name = settings_changed.split("/")[1]
        if table_name != self.model.table_type:
            return
        self.model.default_handler.config = (
            settings_manager.get_table_defaults(self.model.table_type)
        )

    def save_table(self, file_name):
        """Save the table as a tsv file to ``file_name``."""
        if not file_name:
            file_name, _ = QFileDialog.getSaveFileName(
                self.view,
                "Save Table",
                "",
                "TSV Files (*.tsv);;CSV Files (*.csv);;All Files (*)",
            )
        if not file_name:
            return
        if not file_name.endswith((".tsv", ".csv")):
            file_name += ".tsv"
        try:
            save_petab_table(
                self.model.get_df(), file_name, self.model.table_type
            )
        except Exception as e:
            QMessageBox.critical(
                self.view,
                "Error Saving Table",
                f"Failed to save table: {str(e)}",
            )

    def rename_value(
        self, old_id: str, new_id: str, column_names: str | list[str]
    ):
        """Rename the values in the dataframe.

        Triggered by changes in the original observable_df or condition_df id.

        Parameters
        ----------
        old_id:
            The old id, which was changed.
        new_id:
            The new id.
        column_names:
            The column or list of columns in which the id should be changed.
        """
        command = RenameValueCommand(self.model, old_id, new_id, column_names)
        self.undo_stack.push(command)


class MeasurementController(TableController):
    """Controller of the Measurement table."""

    @linter_wrapper
    def check_petab_lint(
        self,
        row_data: pd.DataFrame = None,
        row_name: str = None,
        col_name: str = None,
    ):
        """Check a number of rows of the model with petablint."""
        if row_data is None:
            row_data = self.model.get_df()
        observable_df = self.mother_controller.model.observable.get_df()
        return petab.check_measurement_df(
            row_data,
            observable_df=observable_df,
        )

    def copy_noise_parameters(
        self, observable_id: str, condition_id: str | None = None
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
        matching_rows = measurement_df[
            measurement_df[petab.C.OBSERVABLE_ID] == observable_id
        ]
        if matching_rows.empty:
            return ""
        if not condition_id:
            return matching_rows[petab.C.NOISE_PARAMETERS].iloc[0]
        preferred_row = matching_rows[
            matching_rows[petab.C.SIMULATION_CONDITION_ID] == condition_id
        ]
        if not preferred_row.empty:
            return preferred_row[petab.C.NOISE_PARAMETERS].iloc[0]
        return matching_rows[petab.C.NOISE_PARAMETERS].iloc[0]

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
            "CSV Files (*.csv);;TSV Files (*.tsv)",
        )
        if file_name:
            self.process_data_matrix_file(file_name, "append")

    def process_data_matrix_file(self, file_name, mode, separator=None):
        """Process the data matrix file.

        Upload the data matrix. Then populate the measurement table with the
        new measurements. Additionally, triggers checks for observable_ids.
        """
        try:
            data_matrix = self.load_data_matrix(file_name, separator)
            if data_matrix is None or data_matrix.empty:
                return

            # Resolve time (or dose+time) before potential condition dialog
            df_proc = data_matrix
            dose_col_sel: str | None = None
            time_col = self._detect_time_column(data_matrix)
            if time_col:
                df_proc = data_matrix.rename(columns={time_col: petab.C.TIME})
                cond_dialog = ConditionInputDialog()
                if cond_dialog.exec():
                    conditions = cond_dialog.get_inputs()
                    condition_id = conditions.get(
                        petab.C.SIMULATION_CONDITION_ID, ""
                    )
                    preeq_id = conditions.get(
                        petab.C.PREEQUILIBRATION_CONDITION_ID, ""
                    )
                else:
                    return
            else:
                dose_col_sel, time_choice, preeq_id = (
                    self._resolve_dose_and_time(data_matrix)
                )
                if not dose_col_sel or time_choice is None:
                    self.logger.log_message(
                        "While uploading file as a data matrix: time column "
                        "found and no dose/time selection made.",
                        color="red",
                    )
                    return
                df_proc = data_matrix.copy()
                if (
                    isinstance(time_choice, str)
                    and time_choice.strip().lower() == "inf"
                ):
                    df_proc[petab.C.TIME] = "inf"
                else:
                    try:
                        df_proc[petab.C.TIME] = float(time_choice)
                    except Exception:
                        self.logger.log_message(
                            f"Invalid time value: {time_choice}", color="red"
                        )
                        return
                # No fixed condition_id in dose-response; it's built per-row
                condition_id = ""

            if mode == "overwrite":
                self.model.clear_table()
            self.populate_tables_from_data_matrix(
                df_proc, condition_id, preeq_id, dose_col=dose_col_sel
            )

        except Exception as e:
            self.logger.log_message(
                f"An error occurred while uploading the data matrix: {str(e)}",
                color="red",
            )

    def load_data_matrix(self, file_name, separator=None):
        """Load the data matrix (no hard error on missing 'time')."""
        return pd.read_csv(file_name, delimiter=separator)

    def _detect_time_column(self, df) -> str | None:
        """Return the first matching time column name or None."""
        for c in ("Time", "time", "t"):
            if c in df.columns:
                return c
        return None

    def _rank_dose_candidates(self, df: pd.DataFrame) -> list[str]:
        """Rank columns by likelihood of containing dose/concentration data.

        This method implements a lightweight scoring system to identify
        and rank columns that are most likely to contain dose,
        concentration, or drug-related
        data. The ranking is based on multiple heuristics including column
        naming patterns, data types, value ranges, and statistical
        properties.

        Parameters
        ----------
        df : pd.DataFrame
            Input DataFrame containing columns to be evaluated and ranked.
            Must contain at least one column with data.

        Returns
        -------
        list[str]
            Column names sorted by descending likelihood of containing
            dose data. Columns with higher scores appear first. In case of
            tied scores, columns with fewer unique values are ranked higher.

        Notes
        -----
        The scoring algorithm considers the following criteria:

        - **Name matching** (+2.0 points): Column names containing keywords
          like 'dose', 'conc', 'concentration', 'drug', 'compound', 'stim',
          'input', or patterns like 'u<digit>' (case-insensitive).

        - **Numeric data type** (+1.0 points): Columns with integer or float
          dtype.

        - **Reasonable cardinality** (+0.8 points): Columns with 2-30
          unique non-null values, which is typical for dose series.

        - **Non-negative values** (+0.3 points): All values are >= 0 when
          converted to numeric (dose/concentration values are typically
          non-negative).

        - **Monotonic tendency** (+0.2 points): At least 70% of
          consecutive numeric differences are non-decreasing, indicating
          potential dose escalation patterns. Requires at least 5 non-null
          numeric values.

        Raises
        ------
        AttributeError
            If df does not have the expected pandas DataFrame interface.

        ValueError
            If df is empty or contains no valid columns for evaluation.

        See Also
        --------
        pandas.DataFrame.nunique : Count unique values in each column
        pandas.to_numeric : Convert argument to numeric type
        numpy.diff : Calculate discrete differences along array

        Warning
        -------
        This function uses broad exception handling to ensure robustness when
        processing diverse data types. Individual column evaluation errors are
        silently ignored to prevent failure on edge cases like mixed data types
        or missing values.
        """
        # Compile pattern for dose-related column names
        patt = re.compile(
            r"\b(dose|conc|concentration|drug|compound|stim|input|u\d+)\b",
            re.IGNORECASE,
        )

        scores: dict[str, float] = {}
        for col in df.columns:
            s = 0.0

            # Score based on column name pattern matching
            if patt.search(col or ""):
                s += 2.0

            try:
                # Score based on data type (numeric preferred)
                if df[col].dtype.kind in "if":  # integer or float
                    s += 1.0

                # Score based on reasonable number of unique values
                uniq = df[col].nunique(dropna=True)
                if 2 <= uniq <= 30:  # Reasonable range for dose series?
                    s += 0.8

                # Score based on non-negative values (typical for doses)
                if np.all(
                    pd.to_numeric(df[col], errors="coerce").fillna(0) >= 0
                ):
                    s += 0.3

                # Score based on monotonic tendency (dose escalation pattern)
                ser = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(ser) >= 5:
                    diffs = np.diff(ser.values)
                    if np.mean(diffs >= 0) >= 0.7:  # 70% non-decreasing
                        s += 0.2

            except Exception:  # noqa: S110
                # Silently handle any data processing errors
                pass

            scores[col] = s

        # Sort by score (descending) then by unique count (ascending) for ties
        return [
            c
            for c, _ in sorted(
                scores.items(),
                key=lambda x: (-x[1], df[x[0]].nunique(dropna=True)),
            )
        ]

    def _resolve_dose_and_time(self, df) -> tuple[str | None, str | None, str]:
        """Open dialog with ranked dose suggestions and time choices."""
        header_key = str(hash(tuple(df.columns)))
        settings = settings_manager.settings
        # TODO: rename settings location
        last_dose = settings.value(f"dose/last_choice/{header_key}", "", str)
        suggested = self._rank_dose_candidates(df)
        if last_dose and last_dose in df.columns:
            suggested = [last_dose] + [s for s in suggested if s != last_dose]
        dlg = DoseTimeDialog(
            columns=list(df.columns),
            dose_suggested=suggested,
            parent=self.view if hasattr(self, "view") else None,
        )
        if dlg.exec():
            dose_col, time_text, preeq_id = dlg.get_result()
            if isinstance(time_text, str):
                settings.setValue(f"time/last_choice/{header_key}", time_text)
            return dose_col, time_text, preeq_id or ""
        return None, None, ""

    def _format_dose_value(self, v) -> str:
        """Compact string for dose values to embed in condition IDs."""
        try:
            x = float(v)
            if np.isfinite(x) and x.is_integer():
                return str(int(x))
            return f"{x}".rstrip("0").rstrip(".")
        except Exception:
            return str(v).strip().replace(" ", "_")

    def populate_tables_from_data_matrix(
        self,
        data_matrix,
        condition_id,
        preeq_id: str = "",
        dose_col: str | None = None,
    ):
        """Populate the measurement table from the data matrix."""
        # Build per-row condition IDs if dose_col provided
        condition_ids: Sequence[str] | None = None
        if dose_col and dose_col in data_matrix.columns:
            condition_ids = [
                f"{dose_col}_{self._format_dose_value(v)}"
                for v in data_matrix[dose_col].tolist()
            ]
            for cid in sorted(set(condition_ids)):
                self.model.relevant_id_changed.emit(cid, "", "condition")
        for col in data_matrix.columns:
            if col == petab.C.TIME:
                continue
            if dose_col and col == dose_col:
                continue
            observable_id = col
            self.model.relevant_id_changed.emit(
                observable_id, "", "observable"
            )
            if condition_ids is None:
                self.model.relevant_id_changed.emit(
                    condition_id, "", "condition"
                )
            if preeq_id:
                self.model.relevant_id_changed.emit(preeq_id, "", "condition")
            self.add_measurement_rows(
                data_matrix[[petab.C.TIME, observable_id]],
                observable_id,
                condition_id,
                preeq_id,
                condition_ids=condition_ids,
            )

    def add_measurement_rows(
        self,
        data_matrix,
        observable_id,
        condition_id: str = "",
        preeq_id: str = "",
        condition_ids: Sequence[str] | None = None,
    ):
        """Adds multiple rows to the measurement table."""
        # check number of rows and signal row insertion
        rows = data_matrix.shape[0]
        # get current number of rows
        current_rows = self.model.repository.row_count()
        self.model.insertRows(
            position=None, rows=rows
        )  # Fills the table with empty rows
        top_left = self.model.createIndex(current_rows, 0)
        for i_row, (_, row) in enumerate(data_matrix.iterrows()):
            cid = (
                condition_ids[i_row]
                if condition_ids is not None
                else condition_id
            )
            self.model.fill_row(
                i_row + current_rows,
                data={
                    petab.C.OBSERVABLE_ID: observable_id,
                    petab.C.TIME: row[petab.C.TIME],
                    petab.C.MEASUREMENT: row[observable_id],
                    petab.C.SIMULATION_CONDITION_ID: cid,
                    petab.C.PREEQUILIBRATION_CONDITION_ID: preeq_id,
                },
            )
        bottom = self.model.repository.row_count() - 1
        right = len(self.model.repository.column_names()) - 1
        bottom_right = self.model.createIndex(bottom, right)
        self.model.dataChanged.emit(top_left, bottom_right)
        self.logger.log_message(
            f"Added {rows} measurements to the measurement table.",
            color="green",
        )

    def setup_completers(self):
        """Set completers for the measurement table."""
        table_view = self.view.table_view
        # observableId
        observableId_index = self.model.return_column_index(
            petab.C.OBSERVABLE_ID
        )
        if observableId_index > -1:
            self.completers[petab.C.OBSERVABLE_ID] = ColumnSuggestionDelegate(
                self.mother_controller.model.observable, petab.C.OBSERVABLE_ID
            )
            table_view.setItemDelegateForColumn(
                observableId_index, self.completers[petab.C.OBSERVABLE_ID]
            )
        # preequilibrationConditionId
        preequilibrationConditionId_index = self.model.return_column_index(
            petab.C.PREEQUILIBRATION_CONDITION_ID
        )
        if preequilibrationConditionId_index > -1:
            self.completers[petab.C.PREEQUILIBRATION_CONDITION_ID] = (
                ColumnSuggestionDelegate(
                    self.mother_controller.model.condition,
                    petab.C.CONDITION_ID,
                )
            )
            table_view.setItemDelegateForColumn(
                preequilibrationConditionId_index,
                self.completers[petab.C.PREEQUILIBRATION_CONDITION_ID],
            )
        # simulationConditionId
        simulationConditionId_index = self.model.return_column_index(
            petab.C.SIMULATION_CONDITION_ID
        )
        if simulationConditionId_index > -1:
            self.completers[petab.C.SIMULATION_CONDITION_ID] = (
                ColumnSuggestionDelegate(
                    self.mother_controller.model.condition,
                    petab.C.CONDITION_ID,
                )
            )
            table_view.setItemDelegateForColumn(
                simulationConditionId_index,
                self.completers[petab.C.SIMULATION_CONDITION_ID],
            )
        # noiseParameters
        noiseParameters_index = self.model.return_column_index(
            petab.C.NOISE_PARAMETERS
        )
        if noiseParameters_index > -1:
            self.completers[petab.C.NOISE_PARAMETERS] = (
                SingleSuggestionDelegate(
                    self.model, petab.C.OBSERVABLE_ID, afix="sd_"
                )
            )
            table_view.setItemDelegateForColumn(
                noiseParameters_index,
                self.completers[petab.C.NOISE_PARAMETERS],
            )


class ConditionController(TableController):
    """Controller of the Condition table."""

    condition_2be_renamed = Signal(str, str)  # Signal to mother controller

    def update_handler_model(self):
        """Update the handler model."""
        self.model.default_handler.model = self.model._data_frame

    def setup_connections_specific(self):
        """Setup connections specific to the condition controller.

        Only handles connections from within the table controllers.
        """
        self.model.relevant_id_changed.connect(self.maybe_rename_condition)
        self.overwritten_df.connect(self.update_handler_model)

    @linter_wrapper
    def check_petab_lint(
        self,
        row_data: pd.DataFrame = None,
        row_name: str = None,
        col_name: str = None,
    ):
        """Check a number of rows of the model with petablint."""
        if row_data is None:
            row_data = self.model.get_df()
        observable_df = self.mother_controller.model.observable.get_df()
        sbml_model = self.mother_controller.model.sbml.get_current_sbml_model()
        return petab.check_condition_df(
            row_data,
            observable_df=observable_df,
            model=sbml_model,
        )

    def maybe_rename_condition(self, new_id, old_id):
        """Potentially rename condition_ids in measurement_df.

        Opens a dialog to ask the user if they want to rename the conditions.
        If so, emits a signal to rename the conditions in the measurement_df.
        """
        df = self.mother_controller.measurement_controller.model.get_df()
        if old_id not in df[petab.C.SIMULATION_CONDITION_ID].values:
            return
        reply = QMessageBox.question(
            self.view,
            "Rename Condition",
            f'Do you want to rename condition "{old_id}" to "{new_id}" '
            f"in all measurements?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.logger.log_message(
                f"Renaming condition '{old_id}' to '{new_id}' in all "
                f"measurements",
                color="green",
            )
            self.condition_2be_renamed.emit(old_id, new_id)

    def maybe_add_condition(self, condition_id, old_id=None):
        """Add a condition to the condition table if it does not exist yet."""
        if (
            self.model.repository.get_row_by_id(condition_id)
            or not condition_id
        ):
            return
        # add a row
        self.model.insertRows(position=None, rows=1)
        self.model.fill_row(
            self.model.repository.row_count() - 1,
            data={petab.C.CONDITION_ID: condition_id},
        )
        self.model.cell_needs_validation.emit(
            self.model.repository.row_count() - 1, 0
        )
        self.logger.log_message(
            f"Automatically added condition '{condition_id}' to the condition "
            f"table.",
            color="green",
        )

    def setup_completers(self):
        """Set completers for the condition table."""
        table_view = self.view.table_view
        # conditionName
        conditionName_index = self.model.return_column_index(
            petab.C.CONDITION_NAME
        )
        if conditionName_index > -1:
            self.completers[petab.C.CONDITION_NAME] = SingleSuggestionDelegate(
                self.model, petab.C.CONDITION_ID
            )
            table_view.setItemDelegateForColumn(
                conditionName_index, self.completers[petab.C.CONDITION_NAME]
            )
        for column in self.model.repository.column_names():
            if column in [petab.C.CONDITION_ID, petab.C.CONDITION_NAME]:
                continue
            column_index = self.model.return_column_index(column)
            if column_index > -1:
                self.completers[column] = ColumnSuggestionDelegate(
                    self.model, column, QCompleter.PopupCompletion
                )
                table_view.setItemDelegateForColumn(
                    column_index, self.completers[column]
                )


class ObservableController(TableController):
    """Controller of the Observable table."""

    observable_2be_renamed = Signal(str, str)  # Signal to mother controller

    def update_handler_model(self):
        """Update the handler model."""
        self.model.default_handler.model = self.model._data_frame

    def setup_completers(self):
        """Set completers for the observable table."""
        table_view = self.view.table_view
        # observableName
        observableName_index = self.model.return_column_index(
            petab.C.OBSERVABLE_NAME
        )
        if observableName_index > -1:
            self.completers[petab.C.OBSERVABLE_NAME] = (
                SingleSuggestionDelegate(self.model, petab.C.OBSERVABLE_ID)
            )
            table_view.setItemDelegateForColumn(
                observableName_index, self.completers[petab.C.OBSERVABLE_NAME]
            )
        # observableTransformation
        observableTransformation_index = self.model.return_column_index(
            petab.C.OBSERVABLE_TRANSFORMATION
        )
        if observableTransformation_index > -1:
            self.completers[petab.C.OBSERVABLE_TRANSFORMATION] = (
                ComboBoxDelegate([petab.C.LIN, petab.C.LOG, petab.C.LOG10])
            )
            table_view.setItemDelegateForColumn(
                observableTransformation_index,
                self.completers[petab.C.OBSERVABLE_TRANSFORMATION],
            )
        # noiseFormula
        noiseFormula_index = self.model.return_column_index(
            petab.C.NOISE_FORMULA
        )
        if noiseFormula_index > -1:
            self.completers[petab.C.NOISE_FORMULA] = SingleSuggestionDelegate(
                self.model, petab.C.OBSERVABLE_ID, afix="noiseParameter1_"
            )
            table_view.setItemDelegateForColumn(
                noiseFormula_index, self.completers[petab.C.NOISE_FORMULA]
            )
        # noiseDistribution
        noiseDistribution_index = self.model.return_column_index(
            petab.C.NOISE_DISTRIBUTION
        )
        if noiseDistribution_index > -1:
            self.completers[petab.C.NOISE_DISTRIBUTION] = ComboBoxDelegate(
                [petab.C.NORMAL, petab.C.LAPLACE]
            )
            table_view.setItemDelegateForColumn(
                noiseDistribution_index,
                self.completers[petab.C.NOISE_DISTRIBUTION],
            )

    def setup_connections_specific(self):
        """Setup connections specific to the observable controller.

        Only handles connections from within the table controllers.
        """
        self.model.relevant_id_changed.connect(self.maybe_rename_observable)
        self.overwritten_df.connect(self.update_handler_model)

    @linter_wrapper
    def check_petab_lint(
        self,
        row_data: pd.DataFrame = None,
        row_name: str = None,
        col_name: str = None,
    ):
        """Check a number of rows of the model with petablint."""
        if row_data is None:
            row_data = self.model.get_df()
        return petab.check_observable_df(row_data)

    def maybe_rename_observable(self, new_id, old_id):
        """Potentially rename observable_ids in measurement_df.

        Opens a dialog to ask the user if they want to rename the observables.
        If so, emits a signal to rename the observables in the measurement_df.
        """
        df = self.mother_controller.measurement_controller.model.get_df()
        if old_id not in df[petab.C.OBSERVABLE_ID].values:
            return
        reply = QMessageBox.question(
            self.view,
            "Rename Observable",
            f'Do you want to rename observable "{old_id}" to "{new_id}" '
            f"in all measurements?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.logger.log_message(
                f"Renaming observable '{old_id}' to '{new_id}' in all "
                f"measurements",
                color="green",
            )
            # TODO: connect this signal with the measurement function
            self.observable_2be_renamed.emit(old_id, new_id)

    def maybe_add_observable(self, observable_id, old_id=None):
        """Add an observable to the observable table if it does not exist yet.

        Currently, `old_id` is not used.
        """
        if (
            self.model.repository.get_row_by_id(observable_id)
            or not observable_id
        ):
            return
        # add a row
        self.model.insertRows(position=None, rows=1)
        self.model.fill_row(
            self.model.repository.row_count() - 1,
            data={petab.C.OBSERVABLE_ID: observable_id},
        )
        self.model.cell_needs_validation.emit(
            self.model.repository.row_count() - 1, 0
        )
        self.logger.log_message(
            f"Automatically added observable '{observable_id}' to the "
            f"observable table.",
            color="green",
        )


class ParameterController(TableController):
    """Controller of the Parameter table."""

    def setup_connections_specific(self):
        """Connect signals specific to the parameter controller."""
        self.overwritten_df.connect(self.update_handler_model)

    def update_handler_model(self):
        """Update the handler model."""
        self.model.default_handler.model = self.model._data_frame

    def update_handler_sbml(self):
        self.model.default_handler._sbml_model = (
            self.mother_controller.model.sbml
        )

    def setup_completers(self):
        """Set completers for the parameter table."""
        table_view = self.view.table_view
        # parameterName
        parameterName_index = self.model.return_column_index(
            petab.C.PARAMETER_NAME
        )
        if parameterName_index > -1:
            self.completers[petab.C.PARAMETER_NAME] = SingleSuggestionDelegate(
                self.model, petab.C.PARAMETER_ID
            )
            table_view.setItemDelegateForColumn(
                parameterName_index, self.completers[petab.C.PARAMETER_NAME]
            )
        # parameterScale
        parameterScale_index = self.model.return_column_index(
            petab.C.PARAMETER_SCALE
        )
        if parameterScale_index > -1:
            self.completers[petab.C.PARAMETER_SCALE] = ComboBoxDelegate(
                [petab.C.LIN, petab.C.LOG, petab.C.LOG10]
            )
            table_view.setItemDelegateForColumn(
                parameterScale_index, self.completers[petab.C.PARAMETER_SCALE]
            )
        # lowerBound
        lowerBound_index = self.model.return_column_index(petab.C.LOWER_BOUND)
        if lowerBound_index > -1:
            self.completers[petab.C.LOWER_BOUND] = ColumnSuggestionDelegate(
                self.model, petab.C.LOWER_BOUND, QCompleter.PopupCompletion
            )
            table_view.setItemDelegateForColumn(
                lowerBound_index, self.completers[petab.C.LOWER_BOUND]
            )
        # upperBound
        upperBound_index = self.model.return_column_index(petab.C.UPPER_BOUND)
        if upperBound_index > -1:
            self.completers[petab.C.UPPER_BOUND] = ColumnSuggestionDelegate(
                self.model, petab.C.UPPER_BOUND, QCompleter.PopupCompletion
            )
            table_view.setItemDelegateForColumn(
                upperBound_index, self.completers[petab.C.UPPER_BOUND]
            )
        # estimate
        estimate_index = self.model.return_column_index(petab.C.ESTIMATE)
        if estimate_index > -1:
            self.completers[petab.C.ESTIMATE] = ComboBoxDelegate(["1", "0"])
            table_view.setItemDelegateForColumn(
                estimate_index, self.completers[petab.C.ESTIMATE]
            )
        # parameterId: retrieved from the sbml model
        parameterId_index = self.model.return_column_index(
            petab.C.PARAMETER_ID
        )
        sbml_model = self.mother_controller.model.sbml
        if parameterId_index > -1:
            self.completers[petab.C.PARAMETER_ID] = (
                ParameterIdSuggestionDelegate(
                    par_model=self.model, sbml_model=sbml_model
                )
            )
            table_view.setItemDelegateForColumn(
                parameterId_index, self.completers[petab.C.PARAMETER_ID]
            )

    @linter_wrapper(additional_error_check=True)
    def check_petab_lint(
        self,
        row_data: pd.DataFrame = None,
        row_name: str = None,
        col_name: str = None,
    ):
        """Check a number of rows of the model with petablint."""
        # Validate full parameter table
        if row_data is None:
            row_data = self.model.get_df()
            observable_df = self.mother_controller.model.observable.get_df()
            measurement_df = self.mother_controller.model.measurement.get_df()
            condition_df = self.mother_controller.model.condition.get_df()
            sbml_model = (
                self.mother_controller.model.sbml.get_current_sbml_model()
            )
            return petab.check_parameter_df(
                row_data,
                observable_df=observable_df,
                measurement_df=measurement_df,
                condition_df=condition_df,
                model=sbml_model,
            )

        # Validate a single parameter row
        # In this case, we don't pass any other dataframes/models to avoid
        # false positives due to the incomplete parameter table.
        return petab.check_parameter_df(row_data)


class VisualizationController(TableController):
    """Controller of the Visualization table."""

    def __init__(
        self,
        view: TableViewer,
        model: PandasTableModel,
        logger,
        undo_stack,
        mother_controller,
    ):
        """Initialize the table controller.

        See class:`TableController` for details.
        """
        super().__init__(
            view=view,
            model=model,
            logger=logger,
            undo_stack=undo_stack,
            mother_controller=mother_controller,
        )

    @linter_wrapper(additional_error_check=True)
    def check_petab_lint(
        self,
        row_data: pd.DataFrame = None,
        row_name: str = None,
        col_name: str = None,
    ):
        """Check a number of rows of the model with petablint."""
        problem = self.mother_controller.get_current_problem()
        capture_handler = CaptureLogHandler()
        logger_vis = logging.getLogger("petab.v1.visualize.lint")
        logger_vis.addHandler(capture_handler)
        errors = petab.visualize.lint.validate_visualization_df(problem)
        if not errors:
            return not errors
        captured_output = "<br>&nbsp;&nbsp;&nbsp;&nbsp;".join(
            capture_handler.get_formatted_messages()
        )
        raise ValueError(captured_output)

    def setup_completers(self):
        """Set completers for the visualization table."""
        table_view = self.view.table_view
        # plotTypeSimulation
        index = self.model.return_column_index(petab.C.PLOT_TYPE_SIMULATION)
        if index and index > -1:
            self.completers[petab.C.PLOT_TYPE_SIMULATION] = ComboBoxDelegate(
                [petab.C.LINE_PLOT, petab.C.BAR_PLOT, petab.C.SCATTER_PLOT]
            )
            table_view.setItemDelegateForColumn(
                index, self.completers[petab.C.PLOT_TYPE_SIMULATION]
            )
        # plotTypeData
        index = self.model.return_column_index(petab.C.PLOT_TYPE_DATA)
        if index and index > -1:
            self.completers[petab.C.PLOT_TYPE_DATA] = ComboBoxDelegate(
                [
                    petab.C.MEAN_AND_SD,
                    petab.C.MEAN_AND_SEM,
                    petab.C.REPLICATE,
                    petab.C.PROVIDED,
                ]
            )
            table_view.setItemDelegateForColumn(
                index, self.completers[petab.C.PLOT_TYPE_DATA]
            )
        # datasetId
        index = self.model.return_column_index(petab.C.DATASET_ID)
        if index and index > -1:
            self.completers[petab.C.DATASET_ID] = ColumnSuggestionDelegate(
                self.mother_controller.model.measurement, petab.C.DATASET_ID
            )
            table_view.setItemDelegateForColumn(
                index, self.completers[petab.C.DATASET_ID]
            )
        # yValues
        index = self.model.return_column_index(petab.C.Y_VALUES)
        if index and index > -1:
            self.completers[petab.C.Y_VALUES] = ColumnSuggestionDelegate(
                self.mother_controller.model.observable, petab.C.OBSERVABLE_ID
            )
            table_view.setItemDelegateForColumn(
                index, self.completers[petab.C.Y_VALUES]
            )
        # xScale
        index = self.model.return_column_index(petab.C.X_SCALE)
        if index and index > -1:
            self.completers[petab.C.X_SCALE] = ComboBoxDelegate(
                [petab.C.LIN, petab.C.LOG, petab.C.LOG10, "order"]
            )
            table_view.setItemDelegateForColumn(
                index, self.completers[petab.C.X_SCALE]
            )
        # yScale
        index = self.model.return_column_index(petab.C.Y_SCALE)
        if index and index > -1:
            self.completers[petab.C.Y_SCALE] = ComboBoxDelegate(
                [petab.C.LIN, petab.C.LOG, petab.C.LOG10, "order"]
            )
            table_view.setItemDelegateForColumn(
                index, self.completers[petab.C.Y_SCALE]
            )
