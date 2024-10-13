from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor

from ..C import MEASUREMENT_COLUMNS, OBSERVABLE_COLUMNS, PARAMETER_COLUMNS
from ..utils import validate_value


class PandasTableModel(QAbstractTableModel):
    """Basic table model for a pandas DataFrame."""
    # Signals
    observable_id_changed = Signal(str, str)  # new_id, old_id
    new_log_message = Signal(str, str)  # message, color
    cell_needs_validation = Signal(int, int)  # row, column
    something_changed = Signal(bool)
    inserted_row = Signal(QModelIndex)

    def __init__(self, data_frame, allowed_columns, table_type, parent=None):
        super().__init__(parent)
        self._data_frame = data_frame
        self._allowed_columns = allowed_columns
        self.table_type = table_type
        self._invalid_cells = set()
        self._has_named_index = False

    def rowCount(self, parent=QModelIndex()):
        return self._data_frame.shape[0] + 1  # empty row at the end

    def columnCount(self, parent=QModelIndex()):
        return self._data_frame.shape[1] + 1  # measurement needs other

    def data(self, index, role=Qt.DisplayRole):
        """Return the data at the given index and role for the View."""
        if not index.isValid():
            return None
        row, column = index.row(), index.column()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if row == self._data_frame.shape[0]:
                if column == 0:
                    return f"New {self.table_type}"
                return ""
            if column == 0:
                value = self._data_frame.index[row]
                return str(value)
            value = self._data_frame.iloc[row, column-1]
            return str(value)
        elif role == Qt.BackgroundRole:
            if (row, column) in self._invalid_cells:
                return QColor(Qt.red)
            if (row, column) == (self._data_frame.shape[0], 0):
                return QColor(144, 238, 144, 150)
        return None

    def flags(self, index):
        """Return whether cells are editable and selectable"""
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return the header data for the given section, orientation"""
        if role != Qt.DisplayRole:
            return None
        # role == Qt.DisplayRole
        if orientation == Qt.Horizontal:
            if section == 0:
                return self._data_frame.index.name
            else:
                return self._data_frame.columns[section - 1]
        if orientation == Qt.Vertical:
            return str(section)
        return None

    def insertRows(self, position, rows, parent=QModelIndex()) -> bool:
        """
        Insert new rows at the end of the DataFrame in-place.
        This function always adds rows at the end.

        Parameters:
        -----------
        position: Ignored, as rows are always inserted at the end.
        rows: The number of rows to add.
        parent: Unused in this implementation.

        Returns:
        --------
        bool: True if rows were added successfully.
        """
        end_position = len(self._data_frame)
        self.beginInsertRows(
            QModelIndex(), end_position, end_position + rows - 1
        )

        # In-place row addition using loc
        for i in range(rows):
            # Append an empty row or row with default values using loc
            self._data_frame.loc[end_position + i] = \
                [""] * self._data_frame.shape[1]
        self.endInsertRows()
        return True

    def insertColumn(self, column_name: str):
        """
        Override insertColumn to always add the column at the right (end) of the table,
        and do so in-place on the DataFrame.
        """
        if not (
            column_name in self._allowed_columns or
            self._allowed_columns == {}
        ):  # empty dict means all columns allowed
            self.new_log_message.emit(
                f"Column '{column_name}' not allowed in {self.table_type} table",
                color="orange"
            )
            return False
        position = self._data_frame.shape[1]
        self.beginInsertColumns(QModelIndex(), position, position)
        column_type = self._allowed_columns.get(column_name, "STRING")
        default_value = "" if column_type == "STRING" else 0
        self._data_frame[column_name] = default_value
        self.layoutChanged.emit()

        # End the column insertion process, notifying the view
        self.endInsertColumns()

        return True

    def setData(self, index, value, role=Qt.EditRole):
        col_setoff = 0
        if self._has_named_index:
            col_setoff = 1
        if not (index.isValid() and role == Qt.EditRole):
            return False
        if index.row() == self._data_frame.shape[0]:
            # empty row at the end
            self.insertRows(index.row(), 1)
            self.layoutChanged.emit()
            next_index = self.index(index.row(), 0)
            self.inserted_row.emit(next_index)
        if index.column() == 0 and self._has_named_index:
            return self.handle_named_index(index, value)
        row, column = index.row(), index.column()
        # Handling non-index (regular data) columns
        column_name = self._data_frame.columns[column - col_setoff]
        old_value = self._data_frame.iloc[row, column - col_setoff]
        if value == old_value:
            return False

        if column_name == "observableId":
            self._data_frame.iloc[row, column - col_setoff] = value
            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            self.observable_id_changed.emit(value, old_value)
            self.cell_needs_validation.emit(row, column)
            self.something_changed.emit(True)
            return True

        # Validate data based on expected type
        expected_type = self._allowed_columns.get(column_name)
        if expected_type:
            tried_value = value
            value, error_message = validate_value(
                value, expected_type
            )
            if error_message:
                self.new_log_message.emit(
                    f"Column '{column_name}' expects a value of "
                    f"type {expected_type}, but got '{tried_value}'",
                    color="red"
                )
                return False
        # Set the new value
        self._data_frame.iloc[row, column - col_setoff] = value
        # Validate the row after setting data
        self.cell_needs_validation.emit(row, column)
        self.something_changed.emit(True)
        self.dataChanged.emit(index, index, [Qt.DisplayRole])

        return True

    def handle_named_index(self, index, value):
        """Handle the named index column."""
        pass

    def replace_text(self, old_text: str, new_text: str):
        """Replace text in the table."""
        self._data_frame.replace(old_text, new_text, inplace=True)
        self.layoutChanged.emit()

    def get_df(self):
        """Return the DataFrame."""
        return self._data_frame

    def add_invalid_cell(self, row, column):
        """Add an invalid cell to the set."""
        self._invalid_cells.add((row, column))

    def discard_invalid_cell(self, row, column):
        """Discard an invalid cell from the set."""
        self._invalid_cells.discard((row, column))

    def notify_data_color_change(self, row, column):
        """Notify the view to change the color of some cells"""
        self.dataChanged.emit(
            self.index(row, column),
            self.index(row, column),
            [Qt.BackgroundRole]
        )


class IndexedPandasTableModel(PandasTableModel):
    """Table model for tables with named index."""
    def __init__(self, data_frame, allowed_columns, table_type, parent=None):
        super().__init__(
            data_frame=data_frame,
            allowed_columns=allowed_columns,
            table_type=table_type,
            parent=parent
        )
        self._has_named_index = True

    def handle_named_index(self, index, value):
        """Handle the named index column."""
        row, column = index.row(), index.column()
        old_value = self._data_frame.index[row]
        if value == old_value:
            return False
        if value in self._data_frame.index:
            self.new_log_message.emit(
                f"Duplicate index value '{value}'",
                color="red"
            )
            return False
        try:
            self._data_frame.rename(index={old_value: value}, inplace=True)
            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            self.observable_id_changed.emit(value, old_value)
            self.cell_needs_validation.emit(row, 0)
            self.something_changed.emit(True)
            return True
        except Exception as e:
            self.new_log_message.emit(
                f"Error renaming index value '{old_value}' to '{value}': {e}",
                color="red"
            )
            return False


class MeasurementModel(PandasTableModel):
    """Table model for the measurement data."""
    possibly_new_condition = Signal(str)  # Signal for new condition
    possibly_new_observable = Signal(str)  # Signal for new observable
    def __init__(self, data_frame, parent=None):
        super().__init__(
            data_frame=data_frame,
            allowed_columns=MEASUREMENT_COLUMNS,
            table_type="measurement",
            parent=parent
        )

    def columnCount(self, parent=QModelIndex()):
        return self._data_frame.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        """Return the data at the given index and role for the View."""
        if not index.isValid():
            return None
        row, column = index.row(), index.column()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if row == self._data_frame.shape[0]:
                if column == 0:
                    return f"New {self.table_type}"
                return ""
            value = self._data_frame.iloc[row, column]
            return str(value)
        elif role == Qt.BackgroundRole:
            if (row, column) in self._invalid_cells:
                return QColor(Qt.red)
            if (row, column) == (self._data_frame.shape[0], 0):
                return QColor(144, 238, 144, 150)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return the header data for the given section, orientation"""
        if role != Qt.DisplayRole:
            return None
        # role == Qt.DisplayRole
        if orientation == Qt.Horizontal:
            return self._data_frame.columns[section]
        if orientation == Qt.Vertical:
            return str(section)
        return None

    def fill_row(self, row_position: int, data: dict):
        """Fill a row with data.

        Parameters
        ----------
        row_position:
            The position of the row to fill.
        data:
            The data to fill the row with. Gets updated with default values.
        """
        data_to_add = {
            column_name: "" for column_name in self._data_frame.columns
        }
        data_to_add.update(data)
        # Maybe add default values for missing columns
        self._data_frame.iloc[row_position] = data_to_add


class ObservableModel(IndexedPandasTableModel):
    """Table model for the observable data."""
    def __init__(self, data_frame, parent=None):
        super().__init__(
            data_frame=data_frame,
            allowed_columns=OBSERVABLE_COLUMNS,
            table_type="observable",
            parent=parent
        )

    def fill_row(self, row_position: int, data: dict):
        """Fill a row with data.

        Parameters
        ----------
        row_position:
            The position of the row to fill.
        data:
            The data to fill the row with. Gets updated with default values.
        """
        data_to_add = {
            column_name: "" for column_name in self._data_frame.columns
        }
        data_to_add.update(data)
        # Maybe add default values for missing columns?
        new_index = self._data_frame.index.tolist()
        new_index[row_position] = data_to_add.pop(
            "observableId"
        )
        self._data_frame.index = new_index
        self._data_frame.iloc[row_position] = data_to_add


class ParameterModel(IndexedPandasTableModel):
    """Table model for the parameter data."""
    def __init__(self, data_frame, parent=None):
        super().__init__(
            data_frame=data_frame,
            allowed_columns=PARAMETER_COLUMNS,
            table_type="parameter",
            parent=parent
        )


class ConditionModel(IndexedPandasTableModel):
    """Table model for the condition data."""
    def __init__(self, data_frame, parent=None):
        super().__init__(
            data_frame=data_frame,
            allowed_columns={},
            table_type="condition",
            parent=parent
        )

    def fill_row(self, row_position: int, data: dict):
        """Fill a row with data.

        Parameters
        ----------
        row_position:
            The position of the row to fill.
        data:
            The data to fill the row with. Gets updated with default values.
        """
        data_to_add = {
            column_name: "" for column_name in self._data_frame.columns
        }
        data_to_add.update(data)
        self._data_frame.index[row_position] = data_to_add.pop("conditionId")
        self._data_frame.iloc[row_position] = data_to_add
