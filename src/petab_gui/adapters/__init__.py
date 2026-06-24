"""Adapters layer - infrastructure implementations.

This package contains implementations of domain protocols for specific
technologies:
- PandasTableRepository: pandas DataFrame adapter
- PydanticTableRepository: pydantic models adapter (future)

Adapters sit at the seam - they can be swapped without changing domain or
controller code.
"""

from .pandas_table_repository import PandasTableRepository

__all__ = ["PandasTableRepository"]
