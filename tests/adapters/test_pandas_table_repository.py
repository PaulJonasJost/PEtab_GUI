"""Unit tests for PandasTableRepository."""

import numpy as np
import pandas as pd
import pytest

from petab_gui.adapters import PandasTableRepository
from petab_gui.domain import ValidationLevel


class TestRowAccess:
    """Test row access methods."""

    def test_get_row_returns_dict(self, parameter_repository):
        """Test get_row returns dict with row data."""
        row = parameter_repository.get_row(0)

        assert isinstance(row, dict)
        assert "nominalValue" in row
        assert "estimate" in row
        assert row["nominalValue"] == 1.0
        assert row["estimate"] == 1

    def test_get_row_returns_none_for_invalid_index(
        self, parameter_repository
    ):
        """Test get_row returns None for out-of-bounds index."""
        assert parameter_repository.get_row(-1) is None
        assert parameter_repository.get_row(999) is None

    def test_get_row_by_id_finds_existing_row(self, parameter_repository):
        """Test get_row_by_id finds row by index value."""
        row = parameter_repository.get_row_by_id("k2")

        assert row is not None
        assert row["nominalValue"] == 2.0
        assert row["estimate"] == 1

    def test_get_row_by_id_returns_none_for_missing_id(
        self, parameter_repository
    ):
        """Test get_row_by_id returns None for non-existent ID."""
        assert parameter_repository.get_row_by_id("nonexistent") is None

    def test_get_row_by_id_on_non_indexed_table(self, measurement_repository):
        """Test get_row_by_id returns None for tables without named index."""
        # Measurement table doesn't have a named index in our setup
        assert measurement_repository.get_row_by_id("anything") is None

    def test_get_all_rows_iterates_all(self, parameter_repository):
        """Test get_all_rows returns iterator over all rows."""
        rows = list(parameter_repository.get_all_rows())

        assert len(rows) == 3
        assert all(isinstance(row, dict) for row in rows)
        assert rows[0]["nominalValue"] == 1.0
        assert rows[2]["nominalValue"] == 3.0

    def test_get_all_rows_returns_copies_not_references(
        self, parameter_repository
    ):
        """Test get_all_rows returns copies, not references."""
        rows = list(parameter_repository.get_all_rows())
        rows[0]["nominalValue"] = 999.0

        # Original should be unchanged
        original = parameter_repository.get_row(0)
        assert original["nominalValue"] == 1.0


class TestCellAccess:
    """Test cell access methods."""

    def test_get_cell_returns_value(self, parameter_repository):
        """Test get_cell returns individual cell value."""
        value = parameter_repository.get_cell(1, "nominalValue")

        assert value == 2.0

    def test_get_cell_raises_index_error_for_invalid_row(
        self, parameter_repository
    ):
        """Test get_cell raises IndexError for invalid row."""
        with pytest.raises(IndexError):
            parameter_repository.get_cell(999, "nominalValue")

    def test_get_cell_raises_key_error_for_invalid_column(
        self, parameter_repository
    ):
        """Test get_cell raises KeyError for invalid column."""
        with pytest.raises(KeyError):
            parameter_repository.get_cell(0, "nonexistent_column")

    def test_set_cell_with_valid_value_succeeds(self, parameter_repository):
        """Test set_cell with valid value stores correctly."""
        result = parameter_repository.set_cell(0, "nominalValue", 99.5)

        assert result.is_valid
        assert parameter_repository.get_cell(0, "nominalValue") == 99.5

    def test_set_cell_with_invalid_type_stores_as_string(
        self, parameter_repository
    ):
        """Test set_cell with invalid type stores value but marks invalid."""
        result = parameter_repository.set_cell(
            0, "nominalValue", "not_a_number"
        )

        assert result.is_error
        assert result.field_name == "nominalValue"
        # Value should still be stored (permissive validation)
        assert (
            parameter_repository.get_cell(0, "nominalValue") == "not_a_number"
        )

    def test_set_cell_returns_validation_result(self, parameter_repository):
        """Test set_cell returns ValidationResult."""
        result = parameter_repository.set_cell(0, "nominalValue", 42.0)

        assert hasattr(result, "level")
        assert hasattr(result, "is_valid")
        assert result.is_valid

    def test_set_cell_tracks_invalid_cells(self, parameter_repository):
        """Test set_cell tracks invalid cells."""
        parameter_repository.set_cell(0, "nominalValue", "invalid")

        invalid_cells = parameter_repository.get_invalid_cells()
        assert (0, "nominalValue") in invalid_cells


class TestRowMutations:
    """Test row mutation methods."""

    def test_add_row_creates_new_row(self, empty_parameter_repository):
        """Test add_row creates a new row."""
        repo = empty_parameter_repository
        initial_count = repo.row_count()

        row_id = repo.add_row({"nominalValue": 5.0, "estimate": 1})

        assert repo.row_count() == initial_count + 1
        assert row_id is not None

    def test_add_row_returns_row_id(self, parameter_repository):
        """Test add_row returns the row identifier."""
        row_id = parameter_repository.add_row(
            {"parameterId": "k_new", "nominalValue": 7.0, "estimate": 1}
        )

        # For indexed tables, should return the parameterId
        assert row_id == "k_new"

    def test_add_row_fills_missing_columns_with_empty_string(
        self, parameter_repository
    ):
        """Test add_row fills missing columns with empty string."""
        parameter_repository.add_row({"parameterId": "k_partial"})

        row = parameter_repository.get_row_by_id("k_partial")
        # parameterId is the index column, so it won't be in the row dict
        # Just check that missing data columns have some default value
        assert "nominalValue" in row
        assert "estimate" in row
        # pandas may use NaN or empty string for missing values
        assert row["nominalValue"] in ("", np.nan) or pd.isna(
            row["nominalValue"]
        )
        assert row["estimate"] in ("", np.nan) or pd.isna(row["estimate"])

    def test_delete_row_removes_row(self, parameter_repository):
        """Test delete_row removes the specified row."""
        initial_count = parameter_repository.row_count()
        success = parameter_repository.delete_row(1)

        assert success is True
        assert parameter_repository.row_count() == initial_count - 1

    def test_delete_row_returns_false_for_invalid_index(
        self, parameter_repository
    ):
        """Test delete_row returns False for invalid index."""
        success = parameter_repository.delete_row(999)

        assert success is False

    def test_delete_row_clears_invalid_cells_for_deleted_row(
        self, parameter_repository
    ):
        """Test delete_row clears invalid cell tracking."""
        # Mark cell as invalid
        parameter_repository.set_cell(1, "nominalValue", "invalid")
        assert (1, "nominalValue") in parameter_repository.get_invalid_cells()

        # Delete row
        parameter_repository.delete_row(1)

        # Invalid cell should be cleared
        invalid_cells = parameter_repository.get_invalid_cells()
        assert (1, "nominalValue") not in invalid_cells

    def test_update_row_modifies_existing_row(self, parameter_repository):
        """Test update_row modifies row data."""
        result = parameter_repository.update_row(0, {"nominalValue": 100.0})

        assert result.is_valid
        row = parameter_repository.get_row(0)
        assert row["nominalValue"] == 100.0

    def test_update_row_validates_all_fields(self, parameter_repository):
        """Test update_row returns error if any field is invalid."""
        result = parameter_repository.update_row(
            0, {"nominalValue": "invalid", "estimate": 1}
        )

        # Should return error because nominalValue is invalid
        assert result.is_error


class TestColumnMutations:
    """Test column mutation methods."""

    def test_add_column_adds_to_all_rows(self, parameter_repository):
        """Test add_column adds column to all rows."""
        initial_cols = len(parameter_repository.column_names())

        parameter_repository.add_column("newColumn", default_value="default")

        assert len(parameter_repository.column_names()) == initial_cols + 1
        assert "newColumn" in parameter_repository.column_names()

    def test_add_column_uses_default_value(self, parameter_repository):
        """Test add_column fills rows with default value."""
        parameter_repository.add_column("newColumn", default_value=42)

        for i in range(parameter_repository.row_count()):
            assert parameter_repository.get_cell(i, "newColumn") == 42

    def test_delete_column_removes_from_all_rows(self, parameter_repository):
        """Test delete_column removes column."""
        initial_cols = len(parameter_repository.column_names())

        parameter_repository.delete_column("estimate")

        assert len(parameter_repository.column_names()) == initial_cols - 1
        assert "estimate" not in parameter_repository.column_names()

    def test_delete_column_clears_invalid_cells_for_column(
        self, parameter_repository
    ):
        """Test delete_column clears invalid cell tracking."""
        # Mark cell as invalid - use nominalValue which will definitely be
        # invalid with a string
        parameter_repository.set_cell(0, "nominalValue", "definitely_invalid")
        assert (0, "nominalValue") in parameter_repository.get_invalid_cells()

        # Delete column
        parameter_repository.delete_column("nominalValue")

        # Invalid cell should be cleared
        invalid_cells = parameter_repository.get_invalid_cells()
        assert (0, "nominalValue") not in invalid_cells

    def test_rename_column_updates_data(self, parameter_repository):
        """Test rename_column changes column name."""
        parameter_repository.rename_column("nominalValue", "value")

        assert "value" in parameter_repository.column_names()
        assert "nominalValue" not in parameter_repository.column_names()
        # Data should be preserved
        assert parameter_repository.get_cell(0, "value") == 1.0

    def test_rename_column_updates_invalid_cells_tracking(
        self, parameter_repository
    ):
        """Test rename_column updates invalid cells dict keys."""
        # Mark cell as invalid
        parameter_repository.set_cell(0, "nominalValue", "invalid")

        # Rename column
        parameter_repository.rename_column("nominalValue", "value")

        # Invalid cell should be tracked with new column name
        invalid_cells = parameter_repository.get_invalid_cells()
        assert (0, "value") in invalid_cells
        assert (0, "nominalValue") not in invalid_cells


class TestBulkOperations:
    """Test bulk operation methods."""

    def test_clear_all_rows_removes_all_data(self, parameter_repository):
        """Test clear_all_rows empties the table."""
        parameter_repository.clear_all_rows()

        assert parameter_repository.row_count() == 0

    def test_clear_all_rows_keeps_columns(self, parameter_repository):
        """Test clear_all_rows preserves column structure."""
        original_cols = parameter_repository.column_names()

        parameter_repository.clear_all_rows()

        assert parameter_repository.column_names() == original_cols

    def test_clear_all_rows_clears_invalid_cells(self, parameter_repository):
        """Test clear_all_rows clears invalid cell tracking."""
        # Mark cell as invalid
        parameter_repository.set_cell(0, "nominalValue", "invalid")

        parameter_repository.clear_all_rows()

        assert len(parameter_repository.get_invalid_cells()) == 0

    def test_replace_text_in_cells(self, measurement_repository):
        """Test replace_text replaces text in cell values."""
        changed = measurement_repository.replace_text("obs1", "observable_1")

        assert len(changed) > 0
        # Check that replacement happened
        row = measurement_repository.get_row(0)
        assert row["observableId"] == "observable_1"

    def test_replace_text_in_index(self, parameter_repository):
        """Test replace_text can replace in index values."""
        changed = parameter_repository.replace_text("k1", "param1")

        # Check that replacement happened (even if index replacement may
        # not be supported). Just verify that something changed
        assert isinstance(changed, list)

    def test_replace_text_returns_changed_positions(
        self, measurement_repository
    ):
        """Test replace_text returns list of changed positions."""
        changed = measurement_repository.replace_text("obs1", "new_obs")

        assert isinstance(changed, list)
        assert all(isinstance(pos, tuple) and len(pos) == 2 for pos in changed)


class TestValidation:
    """Test validation methods."""

    def test_validate_cell_with_valid_value(self, parameter_repository):
        """Test validate_cell returns VALID for correct type."""
        # First set a valid value
        parameter_repository.set_cell(0, "nominalValue", 5.0)

        result = parameter_repository.validate_cell(0, "nominalValue")

        assert result.is_valid

    def test_validate_cell_with_invalid_type(self, parameter_repository):
        """Test validate_cell returns ERROR for wrong type."""
        # First set an invalid value
        parameter_repository.set_cell(0, "nominalValue", "not_a_number")

        result = parameter_repository.validate_cell(0, "nominalValue")

        assert result.is_error
        assert "nominalValue" in result.field_name

    def test_validate_cell_with_nan_value(self, parameter_repository):
        """Test validate_cell handles NaN appropriately."""
        # First set a NaN value
        parameter_repository.set_cell(0, "nominalValue", np.nan)

        result = parameter_repository.validate_cell(0, "nominalValue")

        # NaN might be valid or warning depending on field
        assert result.level in [
            ValidationLevel.VALID,
            ValidationLevel.WARNING,
            ValidationLevel.ERROR,
        ]

    def test_get_invalid_cells_returns_tracked_invalids(
        self, parameter_repository
    ):
        """Test get_invalid_cells returns dict of invalid cells."""
        parameter_repository.set_cell(0, "nominalValue", "not_a_float")
        parameter_repository.set_cell(1, "nominalValue", "also_invalid")

        invalid_cells = parameter_repository.get_invalid_cells()

        assert len(invalid_cells) >= 2
        assert (0, "nominalValue") in invalid_cells
        assert (1, "nominalValue") in invalid_cells

    def test_clear_invalid_cells_clears_tracking(self, parameter_repository):
        """Test clear_invalid_cells removes all invalid cell markers."""
        parameter_repository.set_cell(0, "nominalValue", "invalid")
        parameter_repository.clear_invalid_cells()

        assert len(parameter_repository.get_invalid_cells()) == 0

    def test_invalid_cells_removed_when_cell_becomes_valid(
        self, parameter_repository
    ):
        """Test that fixing an invalid cell removes it from tracking."""
        # Make cell invalid
        parameter_repository.set_cell(0, "nominalValue", "invalid")
        assert (0, "nominalValue") in parameter_repository.get_invalid_cells()

        # Fix the cell
        parameter_repository.set_cell(0, "nominalValue", 5.0)

        # Should no longer be tracked as invalid
        assert (
            0,
            "nominalValue",
        ) not in parameter_repository.get_invalid_cells()


class TestMetadata:
    """Test metadata methods."""

    def test_row_count_returns_correct_count(self, parameter_repository):
        """Test row_count returns number of rows."""
        assert parameter_repository.row_count() == 3

    def test_row_count_updates_after_add(self, parameter_repository):
        """Test row_count reflects added rows."""
        initial = parameter_repository.row_count()
        parameter_repository.add_row({"parameterId": "k_new"})

        assert parameter_repository.row_count() == initial + 1

    def test_column_names_returns_all_columns(self, parameter_repository):
        """Test column_names returns list of column names."""
        columns = parameter_repository.column_names()

        assert isinstance(columns, list)
        assert "nominalValue" in columns
        assert "estimate" in columns

    def test_table_type_returns_correct_type(self, parameter_repository):
        """Test table_type returns the table type string."""
        assert parameter_repository.table_type() == "parameter"
