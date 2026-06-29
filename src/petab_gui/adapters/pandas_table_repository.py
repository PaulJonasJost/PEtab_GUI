"""Pandas implementation of TableRepository.

This adapter wraps a pandas DataFrame to implement the TableRepository protocol.
It handles validation, invalid cell tracking, and all CRUD operations while
maintaining compatibility with the existing PandasTableModel behavior.
"""

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from ..C import COLUMNS
from ..domain.validation_result import ValidationLevel, ValidationResult
from ..models.validators import is_invalid, validate_value


class PandasTableRepository:
    """Pandas DataFrame adapter implementing TableRepository protocol.

    This adapter provides the seam between controllers and pandas DataFrames.
    In the future, when migrating to pydantic/PEtab v2.0, this adapter will be
    replaced with PydanticTableRepository, but controllers won't need to change.

    Attributes:
        _data_frame: The underlying pandas DataFrame
        _table_type: Table type (measurement, parameter, etc.)
        _allowed_columns: Column definitions from C.COLUMNS
        _invalid_cells: Set of (row_index, column_name) tuples for invalid cells
    """

    def __init__(
        self,
        data_frame: pd.DataFrame,
        table_type: str,
        allowed_columns: dict | None = None,
    ):
        """Initialize pandas table repository.

        Args:
            data_frame: The pandas DataFrame to wrap
            table_type: Table type identifier (measurement, parameter, etc.)
            allowed_columns: Column definitions (defaults to C.COLUMNS[table_type])
        """
        self._data_frame = data_frame
        self._table_type = table_type
        self._allowed_columns = allowed_columns or COLUMNS.get(table_type, {})
        self._invalid_cells: dict[tuple[int, str], str] = {}

    # Row access
    def get_row(self, index: int) -> dict | None:
        """Get row as dict by position."""
        if not 0 <= index < len(self._data_frame):
            return None

        row = self._data_frame.iloc[index]
        return row.to_dict()

    def get_row_by_id(self, row_id: str) -> dict | None:
        """Get row by identifier (index value)."""
        try:
            if row_id in self._data_frame.index:
                row = self._data_frame.loc[row_id]
                return row.to_dict()
        except (KeyError, TypeError):
            pass
        return None

    def get_all_rows(self) -> Iterable[dict]:
        """Iterate over all rows as dicts."""
        for _, row in self._data_frame.iterrows():
            yield row.to_dict()

    # Cell access
    def get_cell(self, row: int, column: str) -> Any:
        """Get single cell value."""
        return self._data_frame.loc[self._data_frame.index[row], column]

    def set_cell(self, row: int, column: str, value: Any) -> ValidationResult:
        """Set cell value (always succeeds, validates and tracks invalids)."""
        # Get expected type for this column
        expected_type = self._allowed_columns.get(column, {}).get(
            "type", np.object_
        )

        # Validate value
        converted_value, error_message = validate_value(value, expected_type)

        # Always store the value (permissive validation)
        if converted_value is not None:
            self._data_frame.loc[self._data_frame.index[row], column] = (
                converted_value
            )
            value_to_store = converted_value
        else:
            # Store as string if conversion failed
            self._data_frame.loc[self._data_frame.index[row], column] = str(
                value
            )
            value_to_store = str(value)

        # Track invalid cells and return validation result
        cell_key = (row, column)

        if error_message:
            # Validation failed
            self._invalid_cells[cell_key] = error_message
            return ValidationResult.error(
                message=error_message,
                field_name=column,
                expected_type=str(expected_type),
            )

        if is_invalid(value_to_store):
            # Value is None, NaN, or infinity
            error_msg = f"Invalid value: {value_to_store}"
            self._invalid_cells[cell_key] = error_msg
            return ValidationResult.error(
                message=error_msg,
                field_name=column,
            )

        # Value is valid - remove from invalid cells if it was there
        self._invalid_cells.pop(cell_key, None)
        return ValidationResult.valid()

    # Row mutations
    def add_row(self, data: dict) -> str:
        """Add row from dict."""
        # Determine row ID (first column or index)
        row_id = None
        if self._data_frame.index.name:
            # Has named index
            row_id = data.get(self._data_frame.index.name)
        if row_id is None:
            # Use first column as ID
            first_col = self._data_frame.columns[0]
            row_id = data.get(first_col, f"row_{len(self._data_frame)}")

        # Create new row with all columns (fill missing with empty string)
        new_row = {}
        for col in self._data_frame.columns:
            new_row[col] = data.get(col, "")

        # Add to DataFrame
        new_df_row = pd.DataFrame([new_row], index=[row_id])
        self._data_frame = pd.concat(
            [self._data_frame, new_df_row], ignore_index=False
        )

        return str(row_id)

    def delete_row(self, index: int) -> bool:
        """Delete row by position."""
        if not 0 <= index < len(self._data_frame):
            return False

        row_id = self._data_frame.index[index]
        self._data_frame.drop(row_id, inplace=True)

        # Remove invalid cells for this row
        self._invalid_cells = {
            (r, c): msg
            for (r, c), msg in self._invalid_cells.items()
            if r != index
        }

        return True

    def update_row(self, index: int, data: dict) -> ValidationResult:
        """Update entire row."""
        if not 0 <= index < len(self._data_frame):
            return ValidationResult.error("Row index out of bounds")

        # Update each field in the row
        results = []
        for column, value in data.items():
            if column in self._data_frame.columns:
                result = self.set_cell(index, column, value)
                results.append(result)

        # Return error if any field failed, otherwise valid
        for result in results:
            if result.is_error:
                return result
        return ValidationResult.valid()

    # Column mutations
    def add_column(self, column_name: str, default_value: Any = "") -> None:
        """Add column to all rows with default value."""
        self._data_frame[column_name] = default_value

    def delete_column(self, column_name: str) -> None:
        """Remove column from all rows."""
        if column_name in self._data_frame.columns:
            self._data_frame.drop(columns=column_name, inplace=True)

            # Remove invalid cells for this column
            self._invalid_cells = {
                (r, c): msg
                for (r, c), msg in self._invalid_cells.items()
                if c != column_name
            }

    def rename_column(self, old_name: str, new_name: str) -> None:
        """Rename column."""
        if old_name in self._data_frame.columns:
            self._data_frame.rename(columns={old_name: new_name}, inplace=True)

            # Update invalid cells tracking
            updated_invalid = {}
            for (r, c), msg in self._invalid_cells.items():
                if c == old_name:
                    updated_invalid[(r, new_name)] = msg
                else:
                    updated_invalid[(r, c)] = msg
            self._invalid_cells = updated_invalid

    # Bulk operations
    def clear_all_rows(self) -> None:
        """Remove all rows (keeps columns and structure)."""
        self._data_frame.drop(self._data_frame.index, inplace=True)
        self._invalid_cells.clear()

    def replace_text(
        self, old_text: str, new_text: str
    ) -> list[tuple[int, str]]:
        """Replace text in all cells and row IDs."""
        changed_cells = []

        # Replace in cells
        for row_idx in range(len(self._data_frame)):
            for col in self._data_frame.columns:
                value = self._data_frame.iloc[
                    row_idx, self._data_frame.columns.get_loc(col)
                ]
                if str(value) == old_text:
                    self.set_cell(row_idx, col, new_text)
                    changed_cells.append((row_idx, col))

        # Replace in index
        if old_text in self._data_frame.index:
            self._data_frame.rename(index={old_text: new_text}, inplace=True)

        return changed_cells

    # Metadata
    def row_count(self) -> int:
        """Get number of rows."""
        return len(self._data_frame)

    def column_names(self) -> list[str]:
        """Get all column names."""
        return self._data_frame.columns.tolist()

    def table_type(self) -> str:
        """Get table type."""
        return self._table_type

    # DataFrame access (for backward compatibility and bulk operations)
    # NOTE: data_frame property is defined below in "Additional helper methods" section

    # Validation
    def get_invalid_cells(self) -> dict[tuple[int, str], str]:
        """Get all invalid cells."""
        return self._invalid_cells.copy()

    def clear_invalid_cells(self) -> None:
        """Clear all tracked invalid cells."""
        self._invalid_cells.clear()

    def validate_cell(self, row: int, column: str) -> ValidationResult:
        """Validate single cell without modifying data."""
        if not 0 <= row < len(self._data_frame):
            return ValidationResult.error("Row index out of bounds")

        if column not in self._data_frame.columns:
            return ValidationResult.error(f"Column '{column}' does not exist")

        value = self.get_cell(row, column)

        # Get expected type
        expected_type = self._allowed_columns.get(column, {}).get(
            "type", np.object_
        )

        # Validate
        _, error_message = validate_value(value, expected_type)

        if error_message:
            return ValidationResult.error(
                message=error_message,
                field_name=column,
                expected_type=str(expected_type),
            )

        if is_invalid(value):
            return ValidationResult.error(
                message=f"Invalid value: {value}",
                field_name=column,
            )

        return ValidationResult.valid()

    # Additional helper methods for PandasTableModel compatibility
    @property
    def data_frame(self) -> pd.DataFrame:
        """Direct access to underlying DataFrame (for migration period).

        This property exists to ease the transition from direct DataFrame access.
        In the long term, all access should go through repository methods.
        """
        return self._data_frame

    @data_frame.setter
    def data_frame(self, new_df: pd.DataFrame) -> None:
        """Set the underlying DataFrame and clear invalid cell tracking.

        When controllers assign a new DataFrame, we need to update the repository's
        internal state and clear invalid cell tracking.
        """
        self._data_frame = new_df
        self._invalid_cells.clear()
