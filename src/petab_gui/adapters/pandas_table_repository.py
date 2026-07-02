"""Pandas implementation of TableRepository.

This adapter wraps a pandas DataFrame to implement the TableRepository
protocol. It handles validation, invalid cell tracking, and all CRUD
operations while maintaining compatibility with the existing
PandasTableModel behavior.
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

    This adapter provides the seam between controllers and pandas
    DataFrames. In the future, when migrating to pydantic/PEtab v2.0, this
    adapter will be replaced with PydanticTableRepository, but controllers
    won't need to change.

    Attributes:
        _data_frame: The underlying pandas DataFrame
        _table_type: Table type (measurement, parameter, etc.)
        _allowed_columns: Column definitions from C.COLUMNS
        _invalid_cells: Set of (row_index, column_name) tuples for invalid
            cells
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
            allowed_columns: Column definitions (defaults to
                C.COLUMNS[table_type])
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

    def get_row_id(self, row_position: int) -> str:
        """Get row identifier from position."""
        if not 0 <= row_position < len(self._data_frame):
            raise IndexError(f"Row position {row_position} out of bounds")
        return str(self._data_frame.index[row_position])

    def get_row_position(self, row_id: str) -> int:
        """Get row position from identifier."""
        return self._data_frame.index.get_loc(row_id)

    def get_column_position(self, column_name: str) -> int:
        """Get column position from name."""
        return self._data_frame.columns.get_loc(column_name)

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

    def add_row_with_id(
        self, row_id: str, data: dict, preserve_dtypes: bool = True
    ) -> None:
        """Add row with custom identifier and preserve column dtypes."""
        # Store current dtypes if needed
        if preserve_dtypes:
            dtypes = self._data_frame.dtypes.copy()

        # Fill missing columns with empty string
        new_row = {}
        for col in self._data_frame.columns:
            new_row[col] = data.get(col, "")

        # Add row with custom index
        new_df_row = pd.DataFrame([new_row], index=[row_id])
        self._data_frame = pd.concat(
            [self._data_frame, new_df_row], ignore_index=False
        )

        # Restore dtypes if needed
        if preserve_dtypes:
            for col in dtypes.index:
                try:
                    self._data_frame[col] = self._data_frame[col].astype(
                        dtypes[col]
                    )
                except (ValueError, TypeError):
                    # If conversion fails, keep the current dtype
                    pass

    def restore_row_at_position(
        self, position: int, row_id: str, data: dict
    ) -> None:
        """Restore row at exact position with specific ID."""
        # Fill missing columns with empty string
        new_row = {}
        for col in self._data_frame.columns:
            new_row[col] = data.get(col, "")

        # Create new row
        new_df_row = pd.DataFrame([new_row], index=[row_id])

        # Split DataFrame at position and insert
        if position == 0:
            # Insert at beginning
            self._data_frame = pd.concat(
                [new_df_row, self._data_frame], ignore_index=False
            )
        elif position >= len(self._data_frame):
            # Insert at end
            self._data_frame = pd.concat(
                [self._data_frame, new_df_row], ignore_index=False
            )
        else:
            # Insert in middle
            before = self._data_frame.iloc[:position]
            after = self._data_frame.iloc[position:]
            self._data_frame = pd.concat(
                [before, new_df_row, after], ignore_index=False
            )

    def rename_index(self, old_id: str, new_id: str) -> None:
        """Rename row identifier."""
        if old_id in self._data_frame.index:
            self._data_frame.rename(index={old_id: new_id}, inplace=True)

            # Update invalid cells tracking
            updated_invalid = {}
            for (r, c), msg in self._invalid_cells.items():
                # Row indices in _invalid_cells are positions, not IDs
                # So we don't need to update them
                updated_invalid[(r, c)] = msg
            self._invalid_cells = updated_invalid

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

    def insert_column_at(
        self, position: int, column_name: str, default_value: Any = ""
    ) -> None:
        """Insert column at specific position."""
        # Create new column with default value
        self._data_frame.insert(position, column_name, default_value)

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

    def find_cells(
        self,
        pattern: str,
        regex: bool = False,
        case_sensitive: bool = False,
    ) -> list[tuple[int, str, Any]]:
        """Find all cells matching pattern."""
        import re as regex_module

        matches = []

        # Prepare pattern for matching
        if not case_sensitive and not regex:
            pattern_lower = pattern.lower()

        # Search in cells
        for row_idx in range(len(self._data_frame)):
            for col in self._data_frame.columns:
                value = self._data_frame.iloc[
                    row_idx, self._data_frame.columns.get_loc(col)
                ]
                value_str = str(value)

                # Check for match
                if regex:
                    flags = 0 if case_sensitive else regex_module.IGNORECASE
                    if regex_module.search(pattern, value_str, flags):
                        matches.append((row_idx, col, value))
                else:
                    # Simple string matching
                    if case_sensitive:
                        if pattern in value_str:
                            matches.append((row_idx, col, value))
                    else:
                        if pattern_lower in value_str.lower():
                            matches.append((row_idx, col, value))

        # Also search in index
        for row_idx, row_id in enumerate(self._data_frame.index):
            row_id_str = str(row_id)

            # Check for match in index
            if regex:
                flags = 0 if case_sensitive else regex_module.IGNORECASE
                if regex_module.search(pattern, row_id_str, flags):
                    matches.append((row_idx, "_index_", row_id))
            else:
                if case_sensitive:
                    if pattern in row_id_str:
                        matches.append((row_idx, "_index_", row_id))
                else:
                    if pattern_lower in row_id_str.lower():
                        matches.append((row_idx, "_index_", row_id))

        return matches

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
    # NOTE: data_frame property is defined below in
    # "Additional helper methods" section

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

        This property exists to ease the transition from direct DataFrame
        access. In the long term, all access should go through repository
        methods.
        """
        return self._data_frame

    @data_frame.setter
    def data_frame(self, new_df: pd.DataFrame) -> None:
        """Set the underlying DataFrame and clear invalid cell tracking.

        When controllers assign a new DataFrame, we need to update the
        repository's internal state and clear invalid cell tracking.
        """
        self._data_frame = new_df
        self._invalid_cells.clear()
