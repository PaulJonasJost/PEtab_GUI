"""
Controllers
===========

This package contains the controllers of the PEtab edit GUI. Namely:
- The Mother Controller, which is the main controller of the application.
This one has access to all other controllers and handles general tasks as
well as separate view/controller communication.
- The Table Controllers, which are responsible for the table views in the GUI
- The log controller, which handles all logging tasks
- The SBML controller, which handles all SBML tasks
"""
from .mother_controller import MainController
from .table_controllers import MeasurementController, ObservableController, \
    ParameterController, ConditionController, TableController
from .logger_controller import LoggerController
from .sbml_controller import SbmlController