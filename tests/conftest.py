"""Pytest configuration and shared fixtures for repository tests."""

import pandas as pd
import petab
import pytest
from test_helpers import InMemoryTableRepository

from petab_gui.adapters import PandasTableRepository


@pytest.fixture
def sample_parameter_df():
    """Sample parameter DataFrame for testing."""
    return pd.DataFrame(
        {
            "parameterId": ["k1", "k2", "k3"],
            "nominalValue": [1.0, 2.0, 3.0],
            "estimate": [1, 1, 0],
        }
    ).set_index("parameterId")


@pytest.fixture
def sample_measurement_df():
    """Sample measurement DataFrame for testing."""
    return pd.DataFrame(
        {
            "observableId": ["obs1", "obs1", "obs2"],
            "simulationConditionId": ["cond1", "cond1", "cond2"],
            "measurement": [1.5, 2.3, 4.1],
            "time": [0.0, 1.0, 0.0],
        }
    )


@pytest.fixture
def sample_condition_df():
    """Sample condition DataFrame for testing."""
    return pd.DataFrame(
        {
            "conditionId": ["cond1", "cond2"],
            "conditionName": ["Condition 1", "Condition 2"],
        }
    ).set_index("conditionId")


@pytest.fixture
def parameter_repository(sample_parameter_df):
    """PandasTableRepository with parameter data."""
    return PandasTableRepository(sample_parameter_df, "parameter")


@pytest.fixture
def measurement_repository(sample_measurement_df):
    """PandasTableRepository with measurement data."""
    return PandasTableRepository(sample_measurement_df, "measurement")


@pytest.fixture
def condition_repository(sample_condition_df):
    """PandasTableRepository with condition data."""
    return PandasTableRepository(sample_condition_df, "condition")


@pytest.fixture
def empty_parameter_repository():
    """Empty PandasTableRepository for parameter table."""
    df = pd.DataFrame(columns=["parameterId", "nominalValue", "estimate"])
    df = df.set_index("parameterId")
    return PandasTableRepository(df, "parameter")


@pytest.fixture
def in_memory_parameter_repository():
    """InMemoryTableRepository for parameter table."""
    return InMemoryTableRepository(
        "parameter", ["parameterId", "nominalValue", "estimate"]
    )


@pytest.fixture
def in_memory_measurement_repository():
    """InMemoryTableRepository for measurement table."""
    return InMemoryTableRepository(
        "measurement",
        ["observableId", "simulationConditionId", "measurement", "time"],
    )
