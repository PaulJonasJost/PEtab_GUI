"""Domain layer - business logic and protocols.

This package contains:
- Protocols/interfaces that define the seams in the application
- Domain models and value objects
- Validation logic

The domain layer is independent of infrastructure (Qt, pandas) and can be
tested without external dependencies.
"""

from .table_repository import TableRepository
from .validation_result import ValidationLevel, ValidationResult

__all__ = ["TableRepository", "ValidationLevel", "ValidationResult"]
