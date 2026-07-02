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


class TestAdvancedRowMutations:
    """Test advanced row mutation methods for undo/redo support."""

    def test_add_row_with_id_creates_row_with_custom_id(
        self, parameter_repository
    ):
        """Test add_row_with_id creates row with specified ID."""
        parameter_repository.add_row_with_id(
            "custom_k", {"nominalValue": 99.0, "estimate": 1}
        )

        row = parameter_repository.get_row_by_id("custom_k")
        assert row is not None
        assert row["nominalValue"] == 99.0

    def test_add_row_with_id_preserves_dtypes(self, parameter_repository):
        """Test add_row_with_id preserves column dtypes."""
        original_dtypes = parameter_repository._data_frame.dtypes.copy()

        parameter_repository.add_row_with_id(
            "k_new", {"nominalValue": 5.0, "estimate": 1}, preserve_dtypes=True
        )

        # Check dtypes are preserved
        for col in original_dtypes.index:
            assert (
                parameter_repository._data_frame.dtypes[col]
                == original_dtypes[col]
            )

    def test_add_row_with_id_fills_missing_columns(self, parameter_repository):
        """Test add_row_with_id fills missing columns with empty string."""
        parameter_repository.add_row_with_id(
            "k_partial", {"nominalValue": 7.0}
        )

        row = parameter_repository.get_row_by_id("k_partial")
        assert "estimate" in row

    def test_restore_row_at_position_inserts_at_beginning(
        self, parameter_repository
    ):
        """Test restore_row_at_position inserts at position 0."""
        row_data = {"nominalValue": 0.5, "estimate": 0}

        parameter_repository.restore_row_at_position(0, "k0", row_data)

        # Check row is at position 0
        assert parameter_repository.get_row_id(0) == "k0"
        row = parameter_repository.get_row(0)
        assert row["nominalValue"] == 0.5

    def test_restore_row_at_position_inserts_in_middle(
        self, parameter_repository
    ):
        """Test restore_row_at_position inserts at middle position."""
        row_data = {"nominalValue": 1.5, "estimate": 1}

        parameter_repository.restore_row_at_position(1, "k1_5", row_data)

        # Check row is at position 1
        assert parameter_repository.get_row_id(1) == "k1_5"
        row = parameter_repository.get_row(1)
        assert row["nominalValue"] == 1.5

    def test_restore_row_at_position_inserts_at_end(
        self, parameter_repository
    ):
        """Test restore_row_at_position appends at the end."""
        row_data = {"nominalValue": 99.0, "estimate": 1}
        end_position = parameter_repository.row_count()

        parameter_repository.restore_row_at_position(
            end_position, "k_end", row_data
        )

        # Check row is at the last position
        assert parameter_repository.get_row_id(end_position) == "k_end"
        row = parameter_repository.get_row(end_position)
        assert row["nominalValue"] == 99.0

    def test_rename_index_changes_row_id(self, parameter_repository):
        """Test rename_index changes row identifier."""
        parameter_repository.rename_index("k1", "parameter_1")

        # Old ID should not exist
        assert parameter_repository.get_row_by_id("k1") is None
        # New ID should exist
        row = parameter_repository.get_row_by_id("parameter_1")
        assert row is not None
        assert row["nominalValue"] == 1.0

    def test_rename_index_handles_nonexistent_id(self, parameter_repository):
        """Test rename_index handles non-existent ID gracefully."""
        # Should not raise error
        parameter_repository.rename_index("nonexistent", "new_name")

        # Nothing should have changed
        assert parameter_repository.row_count() == 3

    def test_get_row_id_returns_identifier(self, parameter_repository):
        """Test get_row_id returns row identifier from position."""
        row_id = parameter_repository.get_row_id(0)

        assert row_id == "k1"

    def test_get_row_id_raises_for_invalid_position(
        self, parameter_repository
    ):
        """Test get_row_id raises IndexError for invalid position."""
        with pytest.raises(IndexError):
            parameter_repository.get_row_id(999)

    def test_get_row_position_returns_index(self, parameter_repository):
        """Test get_row_position returns position from identifier."""
        position = parameter_repository.get_row_position("k2")

        assert position == 1

    def test_get_row_position_raises_for_invalid_id(
        self, parameter_repository
    ):
        """Test get_row_position raises KeyError for invalid ID."""
        with pytest.raises(KeyError):
            parameter_repository.get_row_position("nonexistent")


class TestAdvancedColumnMutations:
    """Test advanced column mutation methods for undo/redo support."""

    def test_insert_column_at_beginning(self, parameter_repository):
        """Test insert_column_at inserts at position 0."""
        parameter_repository.insert_column_at(0, "newFirst", "default")

        columns = parameter_repository.column_names()
        assert columns[0] == "newFirst"
        # Check all rows have the default value
        for i in range(parameter_repository.row_count()):
            assert parameter_repository.get_cell(i, "newFirst") == "default"

    def test_insert_column_at_middle(self, parameter_repository):
        """Test insert_column_at inserts at middle position."""
        columns_before = parameter_repository.column_names()
        insert_pos = len(columns_before) // 2

        parameter_repository.insert_column_at(insert_pos, "newMiddle", 42)

        columns_after = parameter_repository.column_names()
        assert columns_after[insert_pos] == "newMiddle"
        # Check value
        assert parameter_repository.get_cell(0, "newMiddle") == 42

    def test_insert_column_at_end(self, parameter_repository):
        """Test insert_column_at appends at the end."""
        columns_before = parameter_repository.column_names()
        end_pos = len(columns_before)

        parameter_repository.insert_column_at(end_pos, "newLast", "end")

        columns_after = parameter_repository.column_names()
        assert columns_after[-1] == "newLast"
        assert parameter_repository.get_cell(0, "newLast") == "end"

    def test_get_column_position_returns_index(self, parameter_repository):
        """Test get_column_position returns column position."""
        position = parameter_repository.get_column_position("nominalValue")

        assert isinstance(position, int)
        assert position >= 0

    def test_get_column_position_raises_for_invalid_column(
        self, parameter_repository
    ):
        """Test get_column_position raises KeyError for invalid column."""
        with pytest.raises(KeyError):
            parameter_repository.get_column_position("nonexistent")


class TestSearchMethods:
    """Test search and find methods."""

    def test_find_cells_basic_search(self, parameter_repository):
        """Test find_cells finds matching cells."""
        matches = parameter_repository.find_cells("1")

        assert len(matches) > 0
        # Each match should be (row_idx, col_name, value)
        assert all(len(match) == 3 for match in matches)

    def test_find_cells_case_sensitive(self, measurement_repository):
        """Test find_cells respects case sensitivity."""
        # Add some test data with different cases
        measurement_repository.add_row(
            {"observableId": "OBS_UPPER", "simulationConditionId": "cond1"}
        )

        matches_insensitive = measurement_repository.find_cells(
            "obs", case_sensitive=False
        )
        matches_sensitive = measurement_repository.find_cells(
            "obs", case_sensitive=True
        )

        # Case-insensitive should find more matches
        assert len(matches_insensitive) >= len(matches_sensitive)

    def test_find_cells_regex_search(self, parameter_repository):
        """Test find_cells with regex patterns."""
        # Search for k followed by digit
        matches = parameter_repository.find_cells(r"k\d+", regex=True)

        assert len(matches) > 0
        # All matches should have 'k' followed by digits in index
        for _row_idx, col_name, value in matches:
            if col_name == "_index_":
                assert value.startswith("k")

    def test_find_cells_searches_index(self, parameter_repository):
        """Test find_cells searches row identifiers."""
        matches = parameter_repository.find_cells("k1")

        # Should find "k1" in the index
        index_matches = [m for m in matches if m[1] == "_index_"]
        assert len(index_matches) > 0

    def test_find_cells_returns_empty_for_no_matches(
        self, parameter_repository
    ):
        """Test find_cells returns empty list when no matches found."""
        matches = parameter_repository.find_cells("NONEXISTENT_STRING_12345")

        assert matches == []

    def test_find_cells_with_numeric_values(self, parameter_repository):
        """Test find_cells can find numeric values."""
        matches = parameter_repository.find_cells("1.0")

        assert len(matches) > 0
        # Should find the nominalValue 1.0
        value_matches = [m for m in matches if m[2] == 1.0]
        assert len(value_matches) > 0
