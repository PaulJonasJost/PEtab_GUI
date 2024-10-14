"""Contains the overarching PEtab model class."""
from __future__ import annotations

from pathlib import Path
import petab.v1 as petab
from .sbml_model import SbmlViewerModel
from .pandas_table_model import MeasurementModel, ObservableModel, ParameterModel, ConditionModel


class PEtabModel:
    """PEtab model class.

    This class is responsible for managing the petab Problem, is a container
    for the different data models used in the application and provides
    functionality to test the consistency of the data.

    Attributes
    ----------
    problem: petab.Problem
        The PEtab problem.
    measurement_model: PandasTableModel
        The measurement data model.
    observable_model: PandasTableModel
        The observable data model.
    parameter_model: PandasTableModel
        The parameter data model.
    condition_model: PandasTableModel
        The condition data model.
    sbml_model: SbmlModel
        The SBML model.
    controller: Controller
        The controller of the application.
    """

    def __init__(
        self,
        petab_problem: petab.Problem,
    ):
        """Initialize the PEtab model.

        Parameters
        ----------
        petab_problem: petab.Problem
            The PEtab problem.
        """
        self.problem = petab_problem
        self.measurement = MeasurementModel(
            data_frame=self.problem.measurement_df,
        )
        self.observable = ObservableModel(
            data_frame=self.problem.observable_df,
        )
        self.parameter = ParameterModel(
            data_frame=self.problem.parameter_df,
        )
        self.condition = ConditionModel(
            data_frame=self.problem.condition_df,
        )
        self.sbml = SbmlViewerModel(
            sbml_model=self.problem.model,
        )

    @staticmethod
    def from_petab_yaml(
        petab_yaml_path: str,
    ) -> PEtabModel:
        """Create a PEtab model from a PEtab YAML file.

        Parameters
        ----------
        petab_yaml_path: str
            The path to the PEtab YAML file.

        Returns
        -------
        PEtabModel
            The PEtab model.
        """
        petab_problem = petab.Problem.from_yaml(petab_yaml_path)
        return PEtabModel(petab_problem)

    def test_consistency(self) -> bool:
        """Test the consistency of the data.

        Returns
        -------
        bool
            Whether the data is consistent.
        """
        return petab.lint.lint_problem(self.problem)

    def save(self, directory: str | Path):
        """Save the PEtab model to a directory.

        Parameters
        ----------
        directory: str
            The directory to save the PEtab model to.
        """
        self.problem.to_files(prefix_path=directory)

