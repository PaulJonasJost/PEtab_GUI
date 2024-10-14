"""Constants for the PEtab edit GUI."""
# Measurement Columns
MEASUREMENT_COLUMNS = {
    "observableId": "STRING",
    "preequilibrationConditionId": "STRING",
    "simulationConditionId": "STRING",
    "measurement": "NUMERIC",
    "time": "NUMERIC",
    "observableParameters": "STRING",
    "noiseParameters": "STRING",
    "datasetId": "STRING",
    "replicateId": "STRING"
}

# Observable Columns
OBSERVABLE_COLUMNS = {
    "observableId": "STRING",
    "observableName": "STRING",  # optional
    "observableFormula": "STRING",
    "observableTransformation": "STRING",  # optional
    "noiseFormula": "STRING",
    "noiseDistribution": "STRING"  # optional
}

# Parameter Columns
PARAMETER_COLUMNS = {
    "parameterId": "STRING",
    "parameterName": "STRING",  # optional
    "parameterScale": "STRING",
    "lowerBound": "NUMERIC",
    "upperBound": "NUMERIC",
    "nominalValue": "NUMERIC",
    "estimate": "BOOLEAN",
    "initializationPriorType": "STRING",  # optional
    "initializationPriorParameters": "STRING",  # optional
    "objectivePriorType": "STRING",  # optional
    "objectivePriorParameters": "STRING"  # optional
}

# Condition Columns
CONDITION_COLUMNS = {
    "conditionId": "STRING",
    "conditionName": "STRING"  # optional
    # Additional columns representing different parameters and their values under varying conditions can be added as needed.
}

CONFIG = {
    'window_title': 'My Application',
    'window_size': (800, 600),
    'table_titles': {
        'data': 'Data',
        'parameters': 'Parameters',
        'observables': 'Observables',
        'conditions': 'Conditions'
    },
    'summary_title': 'Summary',
    'buttons': {
        'test_consistency': 'Test Consistency',
        'proceed_optimization': 'Proceed to Optimization'
    }
}
