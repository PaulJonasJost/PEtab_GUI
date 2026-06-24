"""Validation result types for repository operations.

This module defines the structure for validation results returned by repository
operations. The design matches pydantic's validation error structure for future
compatibility when migrating to PEtab v2.0.
"""

from dataclasses import dataclass, field
from enum import Enum


class ValidationLevel(Enum):
    """Validation severity level.

    Attributes:
        VALID: Value is valid
        WARNING: Value is questionable but acceptable
        ERROR: Value is invalid
    """

    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Result of validation operation.

    Rich structure with suggestions for better UX. When validation fails,
    the message explains what's wrong, and suggestions provide alternatives
    (e.g., similar IDs that exist).

    This structure is designed to match pydantic's validation error format,
    making future migration to PEtab v2.0 pydantic models seamless.

    Attributes:
        level: Severity level (VALID, WARNING, ERROR)
        message: Human-readable error/warning message (None if valid)
        suggestions: List of suggested corrections (e.g., similar valid values)
        field_name: Name of the field that was validated
        expected_type: Expected type/format description (e.g., "float", "reference to Observable")

    Example:
        >>> result = ValidationResult(
        ...     level=ValidationLevel.ERROR,
        ...     message="observableId 'obs_typo' not found in observable table",
        ...     suggestions=["obs1", "obs2"],
        ...     field_name="observableId",
        ...     expected_type="reference to Observable"
        ... )
        >>> if result.is_error:
        ...     print(result.message)
        ...     if result.suggestions:
        ...         print(f"Did you mean: {', '.join(result.suggestions)}?")
    """

    level: ValidationLevel
    message: str | None = None
    suggestions: list[str] = field(default_factory=list)
    field_name: str | None = None
    expected_type: str | None = None

    @property
    def is_valid(self) -> bool:
        """Check if validation passed.

        Returns:
            True if level is VALID
        """
        return self.level == ValidationLevel.VALID

    @property
    def is_warning(self) -> bool:
        """Check if validation produced a warning.

        Returns:
            True if level is WARNING
        """
        return self.level == ValidationLevel.WARNING

    @property
    def is_error(self) -> bool:
        """Check if validation failed.

        Returns:
            True if level is ERROR
        """
        return self.level == ValidationLevel.ERROR

    @classmethod
    def valid(cls) -> "ValidationResult":
        """Create a valid result.

        Returns:
            ValidationResult with VALID level

        Example:
            >>> result = ValidationResult.valid()
            >>> assert result.is_valid
        """
        return cls(level=ValidationLevel.VALID)

    @classmethod
    def error(
        cls,
        message: str,
        field_name: str | None = None,
        expected_type: str | None = None,
        suggestions: list[str] | None = None,
    ) -> "ValidationResult":
        """Create an error result.

        Args:
            message: Error message
            field_name: Name of invalid field
            expected_type: Expected type/format
            suggestions: List of suggested corrections

        Returns:
            ValidationResult with ERROR level

        Example:
            >>> result = ValidationResult.error(
            ...     "Invalid value",
            ...     field_name="nominalValue",
            ...     expected_type="float"
            ... )
            >>> assert result.is_error
        """
        return cls(
            level=ValidationLevel.ERROR,
            message=message,
            field_name=field_name,
            expected_type=expected_type,
            suggestions=suggestions or [],
        )

    @classmethod
    def warning(
        cls,
        message: str,
        field_name: str | None = None,
        suggestions: list[str] | None = None,
    ) -> "ValidationResult":
        """Create a warning result.

        Args:
            message: Warning message
            field_name: Name of field with warning
            suggestions: List of suggested improvements

        Returns:
            ValidationResult with WARNING level

        Example:
            >>> result = ValidationResult.warning(
            ...     "Value is unusually large",
            ...     field_name="nominalValue"
            ... )
            >>> assert result.is_warning
        """
        return cls(
            level=ValidationLevel.WARNING,
            message=message,
            field_name=field_name,
            suggestions=suggestions or [],
        )
