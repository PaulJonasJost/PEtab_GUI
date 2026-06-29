"""Unit tests for ValidationResult."""

import pytest

from petab_gui.domain import ValidationLevel, ValidationResult


class TestValidationResult:
    """Test ValidationResult dataclass and properties."""

    def test_valid_result_creation(self):
        """Test creating a valid ValidationResult."""
        result = ValidationResult(level=ValidationLevel.VALID)

        assert result.level == ValidationLevel.VALID
        assert result.message is None
        assert result.suggestions == []
        assert result.field_name is None
        assert result.expected_type is None

    def test_error_result_creation(self):
        """Test creating an error ValidationResult with details."""
        result = ValidationResult(
            level=ValidationLevel.ERROR,
            message="Invalid value",
            field_name="nominalValue",
            expected_type="float",
            suggestions=["1.0", "2.5"],
        )

        assert result.level == ValidationLevel.ERROR
        assert result.message == "Invalid value"
        assert result.field_name == "nominalValue"
        assert result.expected_type == "float"
        assert result.suggestions == ["1.0", "2.5"]

    def test_warning_result_creation(self):
        """Test creating a warning ValidationResult."""
        result = ValidationResult(
            level=ValidationLevel.WARNING, message="Value out of typical range"
        )

        assert result.level == ValidationLevel.WARNING
        assert result.message == "Value out of typical range"

    def test_is_valid_property(self):
        """Test is_valid property returns True only for VALID level."""
        valid = ValidationResult(level=ValidationLevel.VALID)
        error = ValidationResult(level=ValidationLevel.ERROR)
        warning = ValidationResult(level=ValidationLevel.WARNING)

        assert valid.is_valid is True
        assert error.is_valid is False
        assert warning.is_valid is False

    def test_is_error_property(self):
        """Test is_error property returns True only for ERROR level."""
        valid = ValidationResult(level=ValidationLevel.VALID)
        error = ValidationResult(level=ValidationLevel.ERROR)
        warning = ValidationResult(level=ValidationLevel.WARNING)

        assert valid.is_error is False
        assert error.is_error is True
        assert warning.is_error is False

    def test_is_warning_property(self):
        """Test is_warning property returns True only for WARNING level."""
        valid = ValidationResult(level=ValidationLevel.VALID)
        error = ValidationResult(level=ValidationLevel.ERROR)
        warning = ValidationResult(level=ValidationLevel.WARNING)

        assert valid.is_warning is False
        assert error.is_warning is False
        assert warning.is_warning is True

    def test_error_with_suggestions(self):
        """Test error result can store suggestions."""
        result = ValidationResult(
            level=ValidationLevel.ERROR,
            message="Unknown condition ID",
            suggestions=["cond1", "cond2", "cond3"],
        )

        assert len(result.suggestions) == 3
        assert "cond1" in result.suggestions

    def test_error_with_expected_type(self):
        """Test error result can store expected type information."""
        result = ValidationResult(
            level=ValidationLevel.ERROR,
            message="Type mismatch",
            expected_type="float",
            field_name="nominalValue",
        )

        assert result.expected_type == "float"
        assert result.field_name == "nominalValue"

    def test_validation_level_enum_values(self):
        """Test ValidationLevel enum has correct values."""
        assert ValidationLevel.VALID.value == "valid"
        assert ValidationLevel.WARNING.value == "warning"
        assert ValidationLevel.ERROR.value == "error"
