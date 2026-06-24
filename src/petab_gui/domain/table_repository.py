"""Table repository protocol - the seam for data access abstraction.

This protocol defines the interface for table data access, allowing controllers
to work with tables without knowing the underlying data structure (pandas
DataFrames, pydantic models, etc.).

Design principles:
- Data-structure agnostic (works with pandas and pydantic)
- Returns plain dicts (not DataFrames or pydantic models)
- Permissive validation (accepts any input, tracks invalids)
- No Qt dependencies (testable without event loop)
"""

from collections.abc import Iterable
from typing import Any, Protocol

from .validation_result import ValidationResult


class TableRepository(Protocol):
    """Generic repository for table data access.

    This is the seam where data access abstraction happens. Controllers interact
    through this interface, allowing us to swap implementations (pandas →
    pydantic) without changing controller code.

    Adapters that implement this protocol:
    - PandasTableRepository: wraps pandas DataFrame
    - PydanticTableRepository: wraps list of pydantic models (future)
    - InMemoryTableRepository: simple dict-based impl for testing
    """

    # Row access
    def get_row(self, index: int) -> dict | None:
        """Get row as dict by position.

        Args:
            index: Zero-based row position

        Returns:
            Row as dict with column names as keys, or None if out of bounds

        Example:
            >>> repo.get_row(0)
            {'parameterId': 'k1', 'nominalValue': 1.0, 'estimate': True}
        """
        ...

    def get_row_by_id(self, row_id: str) -> dict | None:
        """Get row by identifier (index value).

        Args:
            row_id: The row identifier (value of the index column)

        Returns:
            Row as dict, or None if not found

        Example:
            >>> repo.get_row_by_id('k1')
            {'parameterId': 'k1', 'nominalValue': 1.0, 'estimate': True}
        """
        ...

    def get_all_rows(self) -> Iterable[dict]:
        """Iterate over all rows as dicts.

        Returns:
            Iterator of row dicts

        Example:
            >>> for row in repo.get_all_rows():
            ...     print(row['parameterId'])
        """
        ...

    # Cell access
    def get_cell(self, row: int, column: str) -> Any:
        """Get single cell value.

        Args:
            row: Zero-based row position
            column: Column name

        Returns:
            Cell value (can be any type)

        Raises:
            IndexError: If row is out of bounds
            KeyError: If column doesn't exist
        """
        ...

    def set_cell(self, row: int, column: str, value: Any) -> ValidationResult:
        """Set cell value (always succeeds, validates and tracks invalids).

        This method uses permissive validation - it accepts any input and stores
        it, but returns a ValidationResult indicating whether the value is valid.
        Invalid cells are tracked internally and can be retrieved via
        get_invalid_cells().

        Args:
            row: Zero-based row position
            column: Column name
            value: New value (any type accepted)

        Returns:
            ValidationResult with level (VALID/WARNING/ERROR), message, suggestions

        Example:
            >>> result = repo.set_cell(0, 'nominalValue', 'abc')
            >>> if result.is_error:
            ...     print(f"Invalid: {result.message}")
            ...     # Cell is still set to 'abc', but marked invalid
        """
        ...

    # Row mutations
    def add_row(self, data: dict) -> str:
        """Add row from dict.

        Args:
            data: Row data as dict (column name → value)

        Returns:
            New row ID (value of the ID column)

        Example:
            >>> row_id = repo.add_row({'parameterId': 'k2', 'nominalValue': 2.0})
            >>> print(row_id)  # 'k2'
        """
        ...

    def delete_row(self, index: int) -> bool:
        """Delete row by position.

        Args:
            index: Zero-based row position

        Returns:
            True if row was deleted, False if index was out of bounds
        """
        ...

    def update_row(self, index: int, data: dict) -> ValidationResult:
        """Update entire row.

        Args:
            index: Zero-based row position
            data: New row data (partial updates allowed)

        Returns:
            ValidationResult for the updated row
        """
        ...

    # Column mutations
    def add_column(self, column_name: str, default_value: Any = "") -> None:
        """Add column to all rows with default value.

        Args:
            column_name: Name of new column
            default_value: Value to use for all existing rows (default: "")
        """
        ...

    def delete_column(self, column_name: str) -> None:
        """Remove column from all rows.

        Args:
            column_name: Name of column to remove
        """
        ...

    def rename_column(self, old_name: str, new_name: str) -> None:
        """Rename column.

        Args:
            old_name: Current column name
            new_name: New column name
        """
        ...

    # Bulk operations
    def clear_all_rows(self) -> None:
        """Remove all rows (keeps columns and structure)."""
        ...

    def replace_text(
        self, old_text: str, new_text: str
    ) -> list[tuple[int, str]]:
        """Replace text in all cells and row IDs.

        Args:
            old_text: Text to search for
            new_text: Replacement text

        Returns:
            List of changed (row_index, column_name) positions
        """
        ...

    # Metadata
    def row_count(self) -> int:
        """Get number of rows.

        Returns:
            Number of rows (excluding any 'New' placeholder rows)
        """
        ...

    def column_names(self) -> list[str]:
        """Get all column names.

        Returns:
            List of column names in order
        """
        ...

    def table_type(self) -> str:
        """Get table type.

        Returns:
            Table type identifier (e.g., 'measurement', 'parameter', 'observable')
        """
        ...

    # Validation
    def get_invalid_cells(self) -> dict[tuple[int, str], str]:
        """Get all invalid cells.

        Returns:
            Dict mapping (row_index, column_name) → error_message

        Example:
            >>> invalids = repo.get_invalid_cells()
            >>> print(invalids)
            {(0, 'nominalValue'): 'Expected float, got abc'}
        """
        ...

    def clear_invalid_cells(self) -> None:
        """Clear all tracked invalid cells.

        Useful after bulk operations or when resetting validation state.
        """
        ...

    def validate_cell(self, row: int, column: str) -> ValidationResult:
        """Validate single cell without modifying data.

        Args:
            row: Zero-based row position
            column: Column name

        Returns:
            ValidationResult for the cell's current value
        """
        ...
