"""In-memory implementation of TableRepository for testing.

This simple dict-based implementation allows testing controllers without
pandas or Qt dependencies. It's fast, lightweight, and perfect for unit tests.
"""

from collections.abc import Iterable
from typing import Any

from petab_gui.domain.validation_result import (
    ValidationLevel,
    ValidationResult,
)


class InMemoryTableRepository:
    """Simple in-memory table repository for testing.

    Stores rows as list of dicts. No validation is performed (always returns
    VALID), making it suitable for testing controller logic without worrying
    about data validation details.

    For tests that need validation behavior, use PandasTableRepository instead.

    Attributes:
        rows: List of row dicts
        columns: List of column names
        _table_type: Table type identifier
        _invalid_cells: Tracked invalid cells (for testing validation tracking)
    """

    def __init__(self, table_type: str, columns: list[str] | None = None):
        """Initialize in-memory repository.

        Args:
            table_type: Table type identifier
            columns: Column names (default: empty list)
        """
        self.rows: list[dict] = []
        self.columns: list[str] = columns or []
        self._table_type = table_type
        self._invalid_cells: dict[tuple[int, str], str] = {}

    # Row access
    def get_row(self, index: int) -> dict | None:
        """Get row as dict by position."""
        if 0 <= index < len(self.rows):
            return self.rows[index].copy()
        return None

    def get_row_by_id(self, row_id: str) -> dict | None:
        """Get row by identifier."""
        # Assume first column is ID
        if not self.columns:
            return None

        id_col = self.columns[0]
        for row in self.rows:
            if str(row.get(id_col)) == str(row_id):
                return row.copy()
        return None

    def get_all_rows(self) -> Iterable[dict]:
        """Iterate over all rows as dicts."""
        for row in self.rows:
            yield row.copy()

    def get_row_id(self, row_position: int) -> str:
        """Get row identifier from position."""
        if not 0 <= row_position < len(self.rows):
            raise IndexError(f"Row position {row_position} out of bounds")
        # Use first column value as ID
        if self.columns:
            return str(self.rows[row_position].get(self.columns[0], ""))
        return str(row_position)

    def get_row_position(self, row_id: str) -> int:
        """Get row position from identifier."""
        if not self.columns:
            raise KeyError(f"No columns defined, cannot find row_id: {row_id}")

        id_col = self.columns[0]
        for pos, row in enumerate(self.rows):
            if str(row.get(id_col)) == str(row_id):
                return pos
        raise KeyError(f"Row ID not found: {row_id}")

    def get_column_position(self, column_name: str) -> int:
        """Get column position from name."""
        try:
            return self.columns.index(column_name)
        except ValueError:
            raise KeyError(f"Column not found: {column_name}")

    # Cell access
    def get_cell(self, row: int, column: str) -> Any:
        """Get single cell value."""
        if 0 <= row < len(self.rows):
            return self.rows[row].get(column)
        raise IndexError(f"Row {row} out of bounds")

    def set_cell(self, row: int, column: str, value: Any) -> ValidationResult:
        """Set cell value (always succeeds, no validation)."""
        if not 0 <= row < len(self.rows):
            raise IndexError(f"Row {row} out of bounds")

        self.rows[row][column] = value

        # Add column if it doesn't exist
        if column not in self.columns:
            self.columns.append(column)

        # Always return valid (no validation in test repository)
        return ValidationResult.valid()

    # Row mutations
    def add_row(self, data: dict) -> str:
        """Add row from dict."""
        # Ensure all columns exist in the row
        row = {col: data.get(col, "") for col in self.columns}

        # Add any new columns from data
        for col in data:
            if col not in self.columns:
                self.columns.append(col)
            row[col] = data[col]

        self.rows.append(row)

        # Return ID (first column value or row index)
        if self.columns:
            return str(row.get(self.columns[0], f"row_{len(self.rows) - 1}"))
        return f"row_{len(self.rows) - 1}"

    def delete_row(self, index: int) -> bool:
        """Delete row by position."""
        if 0 <= index < len(self.rows):
            del self.rows[index]
            # Remove invalid cells for this row
            self._invalid_cells = {
                (r if r < index else r - 1, c): msg
                for (r, c), msg in self._invalid_cells.items()
                if r != index
            }
            return True
        return False

    def update_row(self, index: int, data: dict) -> ValidationResult:
        """Update entire row."""
        if not 0 <= index < len(self.rows):
            return ValidationResult.error("Row index out of bounds")

        for column, value in data.items():
            self.rows[index][column] = value
            if column not in self.columns:
                self.columns.append(column)

        return ValidationResult.valid()

    # Column mutations
    def add_column(self, column_name: str, default_value: Any = "") -> None:
        """Add column to all rows with default value."""
        if column_name not in self.columns:
            self.columns.append(column_name)

        for row in self.rows:
            if column_name not in row:
                row[column_name] = default_value

    def delete_column(self, column_name: str) -> None:
        """Remove column from all rows."""
        if column_name in self.columns:
            self.columns.remove(column_name)

        for row in self.rows:
            row.pop(column_name, None)

        # Remove invalid cells for this column
        self._invalid_cells = {
            (r, c): msg
            for (r, c), msg in self._invalid_cells.items()
            if c != column_name
        }

    def rename_column(self, old_name: str, new_name: str) -> None:
        """Rename column."""
        if old_name in self.columns:
            idx = self.columns.index(old_name)
            self.columns[idx] = new_name

        for row in self.rows:
            if old_name in row:
                row[new_name] = row.pop(old_name)

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
        """Remove all rows (keeps columns)."""
        self.rows.clear()
        self._invalid_cells.clear()

    def replace_text(
        self, old_text: str, new_text: str
    ) -> list[tuple[int, str]]:
        """Replace text in all cells."""
        changed_cells = []

        for row_idx, row in enumerate(self.rows):
            for col in self.columns:
                if str(row.get(col)) == old_text:
                    row[col] = new_text
                    changed_cells.append((row_idx, col))

        return changed_cells

    # Metadata
    def row_count(self) -> int:
        """Get number of rows."""
        return len(self.rows)

    def column_names(self) -> list[str]:
        """Get all column names."""
        return self.columns.copy()

    def table_type(self) -> str:
        """Get table type."""
        return self._table_type

    # Validation
    def get_invalid_cells(self) -> dict[tuple[int, str], str]:
        """Get all invalid cells."""
        return self._invalid_cells.copy()

    def clear_invalid_cells(self) -> None:
        """Clear all tracked invalid cells."""
        self._invalid_cells.clear()

    def validate_cell(self, row: int, column: str) -> ValidationResult:
        """Validate single cell (always returns valid in test repository)."""
        if not 0 <= row < len(self.rows):
            return ValidationResult.error("Row index out of bounds")

        if column not in self.columns:
            return ValidationResult.error(f"Column '{column}' does not exist")

        # Always valid (no validation in test repository)
        return ValidationResult.valid()

    # Test helper methods
    def mark_cell_invalid(self, row: int, column: str, message: str) -> None:
        """Mark a cell as invalid (for testing validation tracking).

        Args:
            row: Row index
            column: Column name
            message: Error message
        """
        self._invalid_cells[(row, column)] = message

    def load_rows(self, rows: list[dict]) -> None:
        """Load multiple rows at once (for test setup).

        Args:
            rows: List of row dicts
        """
        self.rows = [row.copy() for row in rows]

        # Update columns from all rows
        all_cols = set()
        for row in rows:
            all_cols.update(row.keys())
        self.columns = list(all_cols)
