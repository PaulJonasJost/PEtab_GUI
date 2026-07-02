"""Adapters layer - Enable swithcing between differend data modes

This package contains implementations of domain protocols for specific
data types:
- PandasTableRepository: pandas DataFrame adapter
- PydanticTableRepository: pydantic models adapter (future)

Adapters can be swapped without changing domain or controller code.
"""

from .pandas_table_repository import PandasTableRepository

__all__ = ["PandasTableRepository"]
