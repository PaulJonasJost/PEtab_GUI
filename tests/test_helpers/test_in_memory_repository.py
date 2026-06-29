"""Unit tests for InMemoryTableRepository."""

import pytest

from test_helpers import InMemoryTableRepository


class TestInMemoryRepository:
    """Test InMemoryTableRepository implementation."""

    def test_add_row_and_get_row(self, in_memory_parameter_repository):
        """Test adding and retrieving rows."""
        repo = in_memory_parameter_repository

        row_id = repo.add_row(
            {"parameterId": "k1", "nominalValue": 1.0, "estimate": 1}
        )

        row = repo.get_row(0)
        assert row is not None
        assert row["parameterId"] == "k1"
        assert row["nominalValue"] == 1.0

    def test_get_row_by_id(self, in_memory_parameter_repository):
        """Test get_row_by_id finds rows by ID."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})
        repo.add_row({"parameterId": "k2", "nominalValue": 2.0, "estimate": 0})

        row = repo.get_row_by_id("k2")

        assert row is not None
        assert row["parameterId"] == "k2"
        assert row["nominalValue"] == 2.0

    def test_set_cell_and_get_cell(self, in_memory_parameter_repository):
        """Test setting and getting cell values."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})

        result = repo.set_cell(0, "nominalValue", 99.0)

        assert result.is_valid
        assert repo.get_cell(0, "nominalValue") == 99.0

    def test_delete_row(self, in_memory_parameter_repository):
        """Test deleting rows."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})
        repo.add_row({"parameterId": "k2", "nominalValue": 2.0, "estimate": 0})

        success = repo.delete_row(0)

        assert success is True
        assert repo.row_count() == 1
        # k2 should now be at index 0
        assert repo.get_row(0)["parameterId"] == "k2"

    def test_add_column(self, in_memory_parameter_repository):
        """Test adding columns."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})

        repo.add_column("newColumn", default_value="default")

        assert "newColumn" in repo.column_names()
        assert repo.get_cell(0, "newColumn") == "default"

    def test_delete_column(self, in_memory_parameter_repository):
        """Test deleting columns."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})

        repo.delete_column("estimate")

        assert "estimate" not in repo.column_names()
        # After deletion, the column shouldn't be accessible
        # InMemory implementation may return None instead of raising KeyError
        row = repo.get_row(0)
        assert "estimate" not in row

    def test_rename_column(self, in_memory_parameter_repository):
        """Test renaming columns."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})

        repo.rename_column("nominalValue", "value")

        assert "value" in repo.column_names()
        assert "nominalValue" not in repo.column_names()
        assert repo.get_cell(0, "value") == 1.0

    def test_clear_all_rows(self, in_memory_parameter_repository):
        """Test clearing all rows."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})
        repo.add_row({"parameterId": "k2", "nominalValue": 2.0, "estimate": 0})

        repo.clear_all_rows()

        assert repo.row_count() == 0
        # Columns should still exist
        assert len(repo.column_names()) > 0

    def test_replace_text(self, in_memory_parameter_repository):
        """Test replace_text functionality."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})
        repo.add_row({"parameterId": "k2", "nominalValue": 2.0, "estimate": 0})

        changed = repo.replace_text("k1", "param1")

        assert len(changed) > 0
        # First row should be updated
        assert repo.get_row(0)["parameterId"] == "param1"
        # Second row should be unchanged
        assert repo.get_row(1)["parameterId"] == "k2"

    def test_load_rows_helper(self):
        """Test load_rows helper method."""
        repo = InMemoryTableRepository(
            "parameter", ["parameterId", "nominalValue", "estimate"]
        )

        repo.load_rows(
            [
                {"parameterId": "k1", "nominalValue": 1.0, "estimate": 1},
                {"parameterId": "k2", "nominalValue": 2.0, "estimate": 0},
            ]
        )

        assert repo.row_count() == 2
        assert repo.get_row(0)["parameterId"] == "k1"
        assert repo.get_row(1)["parameterId"] == "k2"

    def test_mark_cell_invalid_helper(self, in_memory_parameter_repository):
        """Test mark_cell_invalid helper method."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})

        repo.mark_cell_invalid(0, "nominalValue", "Test error message")

        invalid_cells = repo.get_invalid_cells()
        assert (0, "nominalValue") in invalid_cells
        assert invalid_cells[(0, "nominalValue")] == "Test error message"

    def test_get_all_rows(self, in_memory_parameter_repository):
        """Test get_all_rows iterator."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})
        repo.add_row({"parameterId": "k2", "nominalValue": 2.0, "estimate": 0})

        rows = list(repo.get_all_rows())

        assert len(rows) == 2
        assert rows[0]["parameterId"] == "k1"
        assert rows[1]["parameterId"] == "k2"

    def test_update_row(self, in_memory_parameter_repository):
        """Test update_row method."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})

        result = repo.update_row(0, {"nominalValue": 100.0, "estimate": 0})

        assert result.is_valid
        assert repo.get_cell(0, "nominalValue") == 100.0
        assert repo.get_cell(0, "estimate") == 0

    def test_validate_cell(self, in_memory_parameter_repository):
        """Test validate_cell method."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})

        # InMemory repository has permissive validation
        result = repo.validate_cell(0, "nominalValue")

        assert result.is_valid  # Always valid for InMemory

    def test_table_type(self, in_memory_parameter_repository):
        """Test table_type method."""
        repo = in_memory_parameter_repository

        assert repo.table_type() == "parameter"

    def test_clear_invalid_cells(self, in_memory_parameter_repository):
        """Test clear_invalid_cells method."""
        repo = in_memory_parameter_repository
        repo.add_row({"parameterId": "k1", "nominalValue": 1.0, "estimate": 1})
        repo.mark_cell_invalid(0, "nominalValue", "error")

        repo.clear_invalid_cells()

        assert len(repo.get_invalid_cells()) == 0
