"""Store commands for the do/undo functionality.

TRANSITIONAL STATE: Commands are being migrated from direct DataFrame access
to repository pattern. Some operations still use DataFrame directly when:
- Repository doesn't support the operation yet (e.g., positional column insert)
- Index handling requires DataFrame-specific operations
- Dtype preservation requires pandas-specific logic

This hybrid approach will be resolved when migration to PEtab v2.0 is complete.
"""

import numpy as np
import pandas as pd
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QUndoCommand

pd.set_option("future.no_silent_downcasting", True)


def _convert_dtype_with_nullable_int(series, dtype):
    """Convert a series to the specified dtype, handling nullable integers.

    When converting to integer types and the series contains NaN values,
    this function automatically uses pandas nullable integer types (Int64,
    Int32, etc.) instead of numpy integer types which don't support NaN.

    Args:
        series: The pandas Series to convert
        dtype: The target dtype

    Returns:
        The series with the appropriate dtype applied
    """
    # Check if it's already a pandas nullable int type
    is_pandas_nullable_int = isinstance(
        dtype,
        pd.Int64Dtype | pd.Int32Dtype | pd.Int16Dtype | pd.Int8Dtype,
    )

    if is_pandas_nullable_int:
        # Keep pandas nullable integer types as is
        return series.astype(dtype)
    # If column has NaN and dtype is integer, use nullable Int type
    if np.issubdtype(dtype, np.integer) and series.isna().any():
        # Convert numpy int types to pandas nullable Int types
        if dtype == np.int64:
            return series.astype("Int64")
        if dtype == np.int32:
            return series.astype("Int32")
        if dtype == np.int16:
            return series.astype("Int16")
        if dtype == np.int8:
            return series.astype("Int8")
        # Fallback for other integer types
        return series.astype("Int64")
    return series.astype(dtype)


class ModifyColumnCommand(QUndoCommand):
    """Command to add or remove a column in the table.

    This command is used for undo/redo functionality when adding or removing
    columns in a table model.
    """

    def __init__(self, model, column_name, add_mode: bool = True):
        """Initialize the command for adding or removing a column.

        Args:
            model: The table model to modify
            column_name: The name of the column to add or remove
            add_mode: If True, add a column; if False, remove a column
        """
        action = "Add" if add_mode else "Remove"
        super().__init__(
            f"{action} column {column_name} in table {model.table_type}"
        )
        self.model = model
        self.column_name = column_name
        self.add_mode = add_mode
        self.old_values = None
        self.position = None

        if (
            not add_mode
            and column_name in self.model.repository.column_names()
        ):
            self.position = self.model.repository.get_column_position(
                column_name
            )
            # Store old values as dict {row_id: value}
            self.old_values = {}
            for row_idx in range(self.model.repository.row_count()):
                row_id = self.model.repository.get_row_id(row_idx)
                self.old_values[row_id] = self.model.repository.get_cell(
                    row_idx, column_name
                )

    def redo(self):
        """Execute the command to add or remove a column.

        If in add mode, adds a new column to the table.
        If in remove mode, removes the specified column from the table.
        """
        if self.add_mode:
            position = len(self.model.repository.column_names())
            self.model.beginInsertColumns(QModelIndex(), position, position)
            self.model.repository.add_column(
                self.column_name, default_value=""
            )
            self.model.endInsertColumns()
        else:
            self.position = self.model.repository.get_column_position(
                self.column_name
            )
            self.model.beginRemoveColumns(
                QModelIndex(), self.position, self.position
            )
            self.model.repository.delete_column(self.column_name)
            self.model.endRemoveColumns()

    def undo(self):
        """Undo the command, reversing the add or remove operation.

        If the original command was to add a column, this removes it.
        If the original command was to remove a column, this restores it.
        """
        if self.add_mode:
            position = self.model.repository.get_column_position(
                self.column_name
            )
            self.model.beginRemoveColumns(QModelIndex(), position, position)
            self.model.repository.delete_column(self.column_name)
            self.model.endRemoveColumns()
        else:
            self.model.beginInsertColumns(
                QModelIndex(), self.position, self.position
            )
            # Restore column with old values
            # Repository doesn't support positional insert, use DataFrame
            df = self.model._data_frame
            # Convert dict back to Series for insert
            old_values_series = pd.Series(self.old_values)
            df.insert(self.position, self.column_name, old_values_series)
            self.model.endInsertColumns()


class ModifyRowCommand(QUndoCommand):
    """Command to add or remove rows in the table.

    This command is used for undo/redo functionality when adding or removing
    rows in a table model.
    """

    def __init__(
        self, model, row_indices: list[int] | int, add_mode: bool = True
    ):
        """Initialize the command for adding or removing rows.

        Args:
            model: The table model to modify
            row_indices: If add_mode is True, the number of rows to add.
                         If add_mode is False, the indices of rows to remove.
            add_mode: If True, add rows; if False, remove rows
        """
        action = "Add" if add_mode else "Remove"
        super().__init__(f"{action} row(s) in table {model.table_type}")
        self.model = model
        self.add_mode = add_mode
        self.old_rows = None
        self.old_ind_names = None

        if add_mode:
            # Adding: interpret input as count of new rows
            self.row_indices = self._generate_new_indices(row_indices)
        else:
            # Deleting: interpret input as specific index labels
            self.row_indices = (
                row_indices if isinstance(row_indices, list) else [row_indices]
            )
            # Store old rows as list of dicts (repository format)
            self.old_rows = []
            for row_idx in self.row_indices:
                row_data = self.model.repository.get_row(row_idx)
                self.old_rows.append(row_data)

            # Store row IDs using repository
            self.old_ind_names = [
                self.model.repository.get_row_id(idx)
                for idx in self.row_indices
            ]

    def _generate_new_indices(self, count):
        """Generate default row indices based on table type and index type."""
        base = 0
        # Get existing indices through repository
        df = self.model._data_frame
        existing = set(df.index.astype(str))

        indices = []
        while len(indices) < count:
            idx = f"new_{self.model.table_type}_{base}"
            if idx not in existing:
                indices.append(idx)
            base += 1
        self.old_ind_names = indices
        return indices

    def redo(self):
        """Execute the command to add or remove rows.

        If in add mode, adds new rows to the table.
        If in remove mode, removes the specified rows from the table.
        """
        if self.add_mode:
            # Get position before adding rows
            row_count = self.model.repository.row_count()
            position = 0 if row_count == 0 else row_count - 1

            self.model.beginInsertRows(
                QModelIndex(), position, position + len(self.row_indices) - 1
            )

            # Add rows through DataFrame (repository doesn't support custom
            # index yet)
            df = self.model._data_frame
            dtypes = df.dtypes.copy()

            for idx in self.row_indices:
                # Repository doesn't support custom index yet, use DataFrame
                df.loc[idx] = [np.nan] * df.shape[1]

            # Restore dtypes
            if np.any(dtypes != df.dtypes):
                for col, dtype in dtypes.items():
                    if dtype != df.dtypes[col]:
                        df[col] = _convert_dtype_with_nullable_int(
                            df[col], dtype
                        )

            self.model.endInsertRows()
        else:
            # Remove rows
            self.model.beginRemoveRows(
                QModelIndex(), min(self.row_indices), max(self.row_indices)
            )

            # Delete rows through repository
            for row_idx in sorted(self.row_indices, reverse=True):
                self.model.repository.delete_row(row_idx)

            self.model.endRemoveRows()

    def undo(self):
        """Undo the command, reversing the add or remove operation.

        If the original command was to add rows, this removes them.
        If the original command was to remove rows, this restores them.
        """
        df = self.model._data_frame

        if self.add_mode:
            # Remove the rows we added
            positions = [
                self.model.repository.get_row_position(idx)
                for idx in self.row_indices
            ]
            self.model.beginRemoveRows(
                QModelIndex(), min(positions), max(positions)
            )

            # Delete through repository
            for idx in sorted(self.row_indices, reverse=True):
                row_pos = self.model.repository.get_row_position(idx)
                self.model.repository.delete_row(row_pos)

            self.model.endRemoveRows()
        else:
            # Restore deleted rows
            self.model.beginInsertRows(
                QModelIndex(), min(self.row_indices), max(self.row_indices)
            )

            # Restore rows at original positions
            # This requires DataFrame manipulation for index ordering
            restore_index_order = df.index
            for pos, index_name, row_data in zip(
                self.row_indices,
                self.old_ind_names,
                self.old_rows,
                strict=False,
            ):
                restore_index_order = restore_index_order.insert(
                    pos, index_name
                )
                # Restore row - use DataFrame for positioning
                df.loc[index_name] = [
                    row_data.get(col, "") for col in df.columns
                ]
                df.sort_index(
                    inplace=True,
                    key=lambda x: x.map(restore_index_order.get_loc),
                )

            self.model.endInsertRows()


class ModifyDataFrameCommand(QUndoCommand):
    """Command to modify values in a DataFrame.

    This command is used for undo/redo functionality when modifying cell values
    in a table model.
    """

    def __init__(
        self, model, changes: dict[tuple, tuple], description="Modify values"
    ):
        """Initialize the command for modifying DataFrame values.

        Args:
        model:
            The table model to modify
        changes:
            A dictionary mapping (row_key, column_name) to (old_val, new_val)
        description:
            A description of the command for the undo stack
        """
        super().__init__(description)
        self.model = model
        self.changes = changes  # {(row_key, column_name): (old_val, new_val)}

    def redo(self):
        """Execute the command to apply the new values."""
        self._apply_changes(use_new=True)

    def undo(self):
        """Undo the command to restore the old values."""
        self._apply_changes(use_new=False)

    def _apply_changes(self, use_new: bool):
        """Apply changes via repository.

        Args:
        use_new:
            If True, apply the new values; if False, restore the old values
        """
        if not self.changes:
            return

        # Apply changes through repository
        # Repository handles validation and dtype conversion
        # View column offset: +1 if index column is displayed, +0 otherwise
        col_offset = 1 if self.model._has_named_index else 0

        row_positions = []
        col_positions = []

        for (row_id, col_name), (old_val, new_val) in self.changes.items():
            # Select which value to apply
            value = new_val if use_new else old_val

            # Get row position from row_id using repository
            row_pos = self.model.repository.get_row_position(row_id)

            # Apply change through repository (handles validation & dtype)
            self.model.repository.set_cell(row_pos, col_name, value)

            # Track positions for signal emission
            row_positions.append(row_pos)
            col_positions.append(
                self.model.repository.get_column_position(col_name)
                + col_offset
            )

        # Emit dataChanged signal for updated region
        top_left = self.model.index(min(row_positions), min(col_positions))
        bottom_right = self.model.index(max(row_positions), max(col_positions))
        self.model.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])


class RenameIndexCommand(QUndoCommand):
    """Command to rename an index in a DataFrame.

    This command is used for undo/redo functionality when renaming row indices
    in a table model.
    """

    def __init__(self, model, old_index, new_index, model_index):
        """Initialize the command for renaming an index.

        Args:
            model: The table model to modify
            old_index: The original index name
            new_index: The new index name
            model_index: The QModelIndex of the cell being edited
        """
        super().__init__(f"Rename index {old_index} → {new_index}")
        self.model = model
        self.model_index = model_index
        self.old_index = old_index
        self.new_index = new_index

    def redo(self):
        """Execute the command to rename the index."""
        self._apply(self.old_index, self.new_index)

    def undo(self):
        """Undo the command to restore the original index name."""
        self._apply(self.new_index, self.old_index)

    def _apply(self, src, dst):
        """Apply the rename operation.

        Args:
            src: The source index name to rename
            dst: The destination index name
        """
        df = self.model._data_frame
        df.rename(index={src: dst}, inplace=True)
        self.model.dataChanged.emit(
            self.model_index, self.model_index, [Qt.DisplayRole]
        )


class RenameValueCommand(QUndoCommand):
    """Command to rename values in specified columns."""

    def __init__(
        self, model, old_id: str, new_id: str, column_names: str | list[str]
    ):
        super().__init__(f"Rename value {old_id} → {new_id}")
        self.model = model
        self.old_id = old_id
        self.new_id = new_id
        self.column_names = (
            column_names if isinstance(column_names, list) else [column_names]
        )
        self.changes = {}  # {(row_idx, col_name): (old_val, new_val)}

        # Find all matching values through repository
        for row_pos, row_data in enumerate(
            self.model.repository.get_all_rows()
        ):
            for col_name in self.column_names:
                if col_name in row_data and row_data[col_name] == self.old_id:
                    # Get row_id for change tracking
                    row_id = self.model.repository.get_row_id(row_pos)
                    self.changes[(row_id, col_name)] = (
                        self.old_id,
                        self.new_id,
                    )

    def redo(self):
        self._apply_changes(use_new=True)

    def undo(self):
        self._apply_changes(use_new=False)

    def _apply_changes(self, use_new: bool):
        if not self.changes:
            return

        row_positions = []
        col_positions = []

        for (row_id, col_name), (old_val, new_val) in self.changes.items():
            # Get row position using repository
            row_pos = self.model.repository.get_row_position(row_id)

            # Apply change through repository
            value = new_val if use_new else old_val
            self.model.repository.set_cell(row_pos, col_name, value)

            # Track positions for signal emission
            row_positions.append(row_pos)
            col_positions.append(
                self.model.repository.get_column_position(col_name) + 1
            )

        # Emit signals
        top_left = self.model.index(min(row_positions), min(col_positions))
        bottom_right = self.model.index(max(row_positions), max(col_positions))
        self.model.dataChanged.emit(
            top_left, bottom_right, [Qt.DisplayRole, Qt.EditRole]
        )
        self.model.something_changed.emit(True)
