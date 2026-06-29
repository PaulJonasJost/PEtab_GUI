import logging
import os
import re
import tempfile
import zipfile
from functools import partial
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

import petab.v1 as petab
import qtawesome as qta
import yaml
from petab.versions import get_major_version
from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QKeySequence,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QTableView,
    QToolButton,
    QWhatsThis,
    QWidget,
)

from ..C import APP_NAME, REPO_URL
from ..models import PEtabModel, SbmlViewerModel
from ..settings_manager import SettingsDialog, settings_manager
from ..utils import (
    CaptureLogHandler,
    get_selected,
    process_file,
)
from ..views import TaskBar
from ..views.dialogs import NextStepsPanel
from .file_io_controller import FileIOController
from .find_replace_controller import FindReplaceController
from .logger_controller import LoggerController
from .plot_coordinator import PlotCoordinator
from .sbml_controller import SbmlController
from .simulation_controller import SimulationController
from .table_controllers import (
    ConditionController,
    MeasurementController,
    ObservableController,
    ParameterController,
    VisualizationController,
)
from .utils import (
    RecentFilesManager,
    _WhatsThisClickHelp,
    filtered_error,
)
from .validation_controller import ValidationController


class MainController:
    """Main controller class.

    Handles the communication between controllers. Handles general tasks.
    Mother controller to all other controllers. One controller to rule them
    all.
    """

    def __init__(self, view, model: PEtabModel):
        """Initialize the main controller.

        Parameters
        ----------
        view: MainWindow
            The main window.
        model: PEtabModel
            The PEtab model.
        """
        self.undo_stack = QUndoStack()
        self.task_bar = None
        self.view = view
        self.model = model
        self.logger = LoggerController(view.logger_views)
        # CONTROLLERS
        self.measurement_controller = MeasurementController(
            self.view.measurement_dock,
            self.model.measurement,
            self.logger,
            self.undo_stack,
            self,
        )
        self.observable_controller = ObservableController(
            self.view.observable_dock,
            self.model.observable,
            self.logger,
            self.undo_stack,
            self,
        )
        self.parameter_controller = ParameterController(
            self.view.parameter_dock,
            self.model.parameter,
            self.logger,
            self.undo_stack,
            self,
        )
        self.condition_controller = ConditionController(
            self.view.condition_dock,
            self.model.condition,
            self.logger,
            self.undo_stack,
            self,
        )
        self.visualization_controller = VisualizationController(
            self.view.visualization_dock,
            self.model.visualization,
            self.logger,
            self.undo_stack,
            self,
        )
        self.simulation_controller = MeasurementController(
            self.view.simulation_dock,
            self.model.simulation,
            self.logger,
            self.undo_stack,
            self,
        )
        self.sbml_controller = SbmlController(
            self.view.sbml_viewer, self.model.sbml, self.logger, self
        )
        self.controllers = [
            self.measurement_controller,
            self.observable_controller,
            self.parameter_controller,
            self.condition_controller,
            self.sbml_controller,
            self.visualization_controller,
            self.simulation_controller,
        ]
        # File I/O Controller
        self.file_io = FileIOController(self)
        # Plot Coordinator
        self.plot_coordinator = PlotCoordinator(self)
        # Validation Controller
        self.validation = ValidationController(self)
        # Simulation Controller
        self.simulation = SimulationController(self)
        # Find/Replace Controller
        self.find_replace_controller = FindReplaceController(
            {
                "Observable Table": self.observable_controller,
                "Condition Table": self.condition_controller,
                "Parameter Table": self.parameter_controller,
                "Measurement Table": self.measurement_controller,
                "Visualization Table": self.visualization_controller,
                "Simulation Table": self.simulation_controller,
            }
        )
        # Recent Files
        self.recent_files_manager = RecentFilesManager(max_files=10)
        # Checkbox states for Find + Replace
        self.petab_checkbox_states = {
            "measurement": False,
            "observable": False,
            "parameter": False,
            "condition": False,
            "visualization": False,
            "simulation": False,
        }
        self.sbml_checkbox_states = {"sbml": False, "antimony": False}
        self.unsaved_changes = False
        # Next Steps Panel
        self.next_steps_panel = NextStepsPanel(self.view)
        self.next_steps_panel.dont_show_again_changed.connect(
            self._handle_next_steps_dont_show_again
        )
        self.filter = QLineEdit()
        self.filter_active = {}  # Saves which tables the filter applies to
        self.actions = self.setup_actions()
        self.view.setup_toolbar(self.actions)

        # Initialize plotter through plot coordinator
        self.plot_coordinator.init_plotter()
        self.plotter = self.plot_coordinator.plotter
        self.setup_connections()
        self.setup_task_bar()
        self.setup_context_menu()

    @property
    def window_title(self):
        """Return the window title based on the model."""
        if isinstance(self.model.sbml, SbmlViewerModel):
            return self.model.sbml.model_id
        return APP_NAME

    def setup_context_menu(self):
        """Sets up context menus for the tables."""
        for controller in self.controllers:
            if controller == self.sbml_controller:
                continue
            controller.setup_context_menu(self.actions)

    def setup_task_bar(self):
        """Create shortcuts for the main window."""
        self.view.task_bar = TaskBar(self.view, self.actions)
        self.task_bar = self.view.task_bar

    # CONNECTIONS
    def setup_connections(self):
        """Setup connections.

        Sets all connections that communicate from one different
        Models/Views/Controllers to another. Also sets general connections.
        """
        # Rename Observable
        self.observable_controller.observable_2be_renamed.connect(
            partial(
                self.measurement_controller.rename_value,
                column_names="observableId",
            )
        )
        self.observable_controller.observable_2be_renamed.connect(
            partial(
                self.visualization_controller.rename_value,
                column_names="yValues",
            )
        )
        # Maybe TODO: add renaming dataset id?
        # Rename Condition
        self.condition_controller.condition_2be_renamed.connect(
            partial(
                self.measurement_controller.rename_value,
                column_names=[
                    "simulationConditionId",
                    "preequilibrationConditionId",
                ],
            )
        )
        # Plotting Disable Temporarily
        for controller in self.controllers:
            if controller == self.sbml_controller:
                continue
            controller.model.plotting_needs_break.connect(
                self.plotter.disable_plotting
            )
        # Add new condition or observable
        self.model.measurement.relevant_id_changed.connect(
            lambda x, y, z: self.observable_controller.maybe_add_observable(
                x, y
            )
            if z == "observable"
            else self.condition_controller.maybe_add_condition(x, y)
            if z == "condition"
            else None
        )
        # Plot selection synchronization
        self.view.measurement_dock.table_view.selectionModel().selectionChanged.connect(
            self.plot_coordinator._on_table_selection_changed
        )
        self.view.simulation_dock.table_view.selectionModel().selectionChanged.connect(
            self.plot_coordinator._on_simulation_selection_changed
        )
        # Unsaved Changes
        self.model.measurement.something_changed.connect(
            self.unsaved_changes_change
        )
        self.model.observable.something_changed.connect(
            self.unsaved_changes_change
        )
        self.model.parameter.something_changed.connect(
            self.unsaved_changes_change
        )
        self.model.condition.something_changed.connect(
            self.unsaved_changes_change
        )
        self.model.visualization.something_changed.connect(
            self.unsaved_changes_change
        )
        self.model.simulation.something_changed.connect(
            self.unsaved_changes_change
        )
        self.model.sbml.something_changed.connect(self.unsaved_changes_change)
        # Visibility
        self.sync_visibility_with_actions()
        # Recent Files
        self.recent_files_manager.open_file.connect(
            partial(self.file_io.open_file, mode="overwrite")
        )
        # Settings logging
        settings_manager.new_log_message.connect(self.logger.log_message)
        # Update Parameter SBML Model
        self.sbml_controller.overwritten_model.connect(
            self.parameter_controller.update_handler_sbml
        )
        # Plotting update connections
        for controller in [
            self.measurement_controller,
            self.condition_controller,
            self.visualization_controller,
            self.simulation_controller,
        ]:
            controller.overwritten_df.connect(
                self.plot_coordinator._schedule_plot_update
            )
        self.view.file_open_requested.connect(
            partial(self.file_io.open_file, mode="overwrite")
        )
        self.view.close_requested.connect(self.maybe_close)

    def setup_actions(self):
        """Setup actions for the main controller."""
        actions = {
            "close": QAction(qta.icon("mdi6.close"), "&Close", self.view)
        }
        # Close
        actions["close"].setShortcut(QKeySequence.Close)
        actions["close"].triggered.connect(self.view.close)
        # New File
        actions["new"] = QAction(
            qta.icon("mdi6.file-document"), "&New", self.view
        )
        actions["new"].setShortcut(QKeySequence.New)
        actions["new"].triggered.connect(self.file_io.new_file)
        # Open File
        actions["open"] = QAction(
            qta.icon("mdi6.folder-open"), "&Open...", self.view
        )
        actions["open"].setShortcut(QKeySequence.Open)
        actions["open"].triggered.connect(
            partial(self.file_io.open_file, mode="overwrite")
        )
        # Add File
        actions["add"] = QAction(qta.icon("mdi6.table-plus"), "Add", self.view)
        actions["add"].setShortcut("Ctrl+Shift+O")
        actions["add"].triggered.connect(
            partial(self.file_io.open_file, mode="append")
        )
        # Load Examples
        actions["load_example_boehm"] = QAction(
            qta.icon("mdi6.book-open-page-variant"),
            "Load Example: Boehm",
            self.view,
        )
        actions["load_example_boehm"].triggered.connect(
            partial(self.file_io.load_example, "Boehm")
        )
        actions["load_example_simple"] = QAction(
            qta.icon("mdi6.book-open-page-variant"),
            "Load Example: Simple Conversion",
            self.view,
        )
        actions["load_example_simple"].triggered.connect(
            partial(self.file_io.load_example, "Simple_Conversion")
        )
        # Save
        actions["save"] = QAction(
            qta.icon("mdi6.content-save-all"), "&Save As...", self.view
        )
        actions["save"].setShortcut(QKeySequence.Save)
        actions["save"].triggered.connect(self.file_io.save_model)
        actions["save_single_table"] = QAction(
            qta.icon("mdi6.table-arrow-down"), "Save This Table", self.view
        )
        actions["save_single_table"].triggered.connect(
            self.file_io.save_single_table
        )
        actions["save_sbml"] = QAction(
            qta.icon("mdi6.file-code"), "Export SBML Model", self.view
        )
        actions["save_sbml"].triggered.connect(self.file_io.save_sbml_model)
        # Find + Replace
        actions["find"] = QAction(qta.icon("mdi6.magnify"), "Find", self.view)
        actions["find"].setShortcut(QKeySequence.Find)
        actions["find"].triggered.connect(self.find)
        actions["find+replace"] = QAction(
            qta.icon("mdi6.find-replace"), "Find/Replace", self.view
        )
        sequence = QKeySequence(QKeySequence.Replace)
        if sequence.isEmpty():
            sequence = QKeySequence("Ctrl+R")
        actions["find+replace"].setShortcut(sequence)
        actions["find+replace"].triggered.connect(self.replace)
        # Copy / Paste
        actions["copy"] = QAction(
            qta.icon("mdi6.content-copy"), "Copy", self.view
        )
        actions["copy"].setShortcut(QKeySequence.Copy)
        actions["copy"].triggered.connect(self.copy_to_clipboard)
        actions["paste"] = QAction(
            qta.icon("mdi6.content-paste"), "Paste", self.view
        )
        actions["paste"].setShortcut(QKeySequence.Paste)
        actions["paste"].triggered.connect(self.paste_from_clipboard)
        actions["cut"] = QAction(
            qta.icon("mdi6.content-cut"), "&Cut", self.view
        )
        actions["cut"].setShortcut(QKeySequence.Cut)
        actions["cut"].triggered.connect(self.cut)
        # add/delete row
        actions["add_row"] = QAction(
            qta.icon("mdi6.table-row-plus-after"), "Add Row", self.view
        )
        actions["add_row"].triggered.connect(self.add_row)
        actions["delete_row"] = QAction(
            qta.icon("mdi6.table-row-remove"), "Delete Row(s)", self.view
        )
        actions["delete_row"].triggered.connect(self.delete_rows)
        # add/delete column
        actions["add_column"] = QAction(
            qta.icon("mdi6.table-column-plus-after"),
            "Add Column...",
            self.view,
        )
        actions["add_column"].triggered.connect(self.add_column)
        actions["delete_column"] = QAction(
            qta.icon("mdi6.table-column-remove"), "Delete Column(s)", self.view
        )
        actions["delete_column"].triggered.connect(self.delete_column)
        # check petab model
        actions["check_petab"] = QAction(
            qta.icon("mdi6.checkbox-multiple-marked-circle-outline"),
            "Check PEtab",
            self.view,
        )
        actions["check_petab"].triggered.connect(self.validation.check_model)
        actions["reset_model"] = QAction(
            qta.icon("mdi6.restore"), "Reset SBML Model", self.view
        )
        actions["reset_model"].triggered.connect(
            self.sbml_controller.reset_to_original_model
        )
        # Recent Files
        actions["recent_files"] = self.recent_files_manager.tool_bar_menu

        # simulate action
        actions["simulate"] = QAction(
            qta.icon("mdi6.play"), "Simulate", self.view
        )
        actions["simulate"].triggered.connect(self.simulation.simulate)

        # Filter widget
        filter_widget = QWidget()
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_widget.setLayout(filter_layout)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter...")
        filter_layout.addWidget(self.filter_input)
        for table_n, table_name in zip(
            ["m", "p", "o", "c", "v", "s"],
            [
                "measurement",
                "parameter",
                "observable",
                "condition",
                "visualization",
                "simulation",
            ],
            strict=False,
        ):
            tool_button = QToolButton()
            icon = qta.icon(
                f"mdi6.alpha-{table_n}",
                "mdi6.filter",
                options=[
                    {"scale_factor": 1.5, "offset": (-0.2, -0.2)},
                    {"off": "mdi6.filter-off", "offset": (0.3, 0.3)},
                ],
            )
            tool_button.setIcon(icon)
            tool_button.setCheckable(True)
            tool_button.setChecked(True)
            tool_button.setToolTip(f"Filter for {table_name} table")
            filter_layout.addWidget(tool_button)
            self.filter_active[table_name] = tool_button
            self.filter_active[table_name].toggled.connect(self.filter_table)
        actions["filter_widget"] = filter_widget
        self.filter_input.textChanged.connect(self.filter_table)

        # show/hide elements
        for element in [
            "measurement",
            "observable",
            "parameter",
            "condition",
            "visualization",
            "simulation",
        ]:
            actions[f"show_{element}"] = QAction(
                f"{element.capitalize()} Table", self.view
            )
            actions[f"show_{element}"].setCheckable(True)
            actions[f"show_{element}"].setChecked(True)
        actions["show_logger"] = QAction("Info", self.view)
        actions["show_logger"].setCheckable(True)
        actions["show_logger"].setChecked(True)
        actions["show_plot"] = QAction("Data Plot", self.view)
        actions["show_plot"].setCheckable(True)
        actions["show_plot"].setChecked(True)
        actions["show_sbml_editor"] = QAction("SBML Editor", self.view)
        actions["show_sbml_editor"].setCheckable(True)
        actions["show_sbml_editor"].setChecked(True)

        # What's This action
        actions["whats_this"] = QAction(
            qta.icon("mdi6.help-circle"), "Enter Help Mode", self.view
        )
        actions["whats_this"].setCheckable(True)
        actions["whats_this"].setShortcut("Shift+F1")
        self._whats_this_filter = _WhatsThisClickHelp(actions["whats_this"])
        actions["whats_this"].toggled.connect(self._toggle_whats_this_mode)

        # About action
        actions["about"] = QAction(
            qta.icon("mdi6.information"), "&About", self.view
        )
        actions["about"].triggered.connect(self.about)

        # connect actions
        actions["reset_view"] = QAction(
            qta.icon("mdi6.view-grid-plus"), "Reset View", self.view
        )
        actions["reset_view"].triggered.connect(self.view.default_view)
        # Clear Log
        actions["clear_log"] = QAction(
            qta.icon("mdi6.delete"), "Clear Log", self.view
        )
        actions["clear_log"].triggered.connect(self.logger.clear_log)
        # Settings
        actions["settings"] = QAction(
            qta.icon("mdi6.cog"), "Settings", self.view
        )
        actions["settings"].triggered.connect(self.open_settings)

        # Opening the PEtab documentation
        actions["open_documentation"] = QAction(
            qta.icon("mdi6.web"), "View PEtab Documentation", self.view
        )
        actions["open_documentation"].triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl(
                    "https://petab.readthedocs.io/en/latest/v1/"
                    "documentation_data_format.html"
                )
            )
        )

        # Show next steps panel action
        actions["next_steps"] = QAction(
            qta.icon("mdi6.lightbulb-on"), "Possible next steps...", self.view
        )
        actions["next_steps"].triggered.connect(self._show_next_steps_panel)

        # Undo / Redo
        actions["undo"] = QAction(qta.icon("mdi6.undo"), "&Undo", self.view)
        actions["undo"].setShortcut(QKeySequence.Undo)
        actions["undo"].triggered.connect(self.undo_stack.undo)
        actions["undo"].setEnabled(self.undo_stack.canUndo())
        self.undo_stack.canUndoChanged.connect(actions["undo"].setEnabled)
        actions["redo"] = QAction(qta.icon("mdi6.redo"), "&Redo", self.view)
        actions["redo"].setShortcut(QKeySequence.Redo)
        actions["redo"].triggered.connect(self.undo_stack.redo)
        actions["redo"].setEnabled(self.undo_stack.canRedo())
        self.undo_stack.canRedoChanged.connect(actions["redo"].setEnabled)
        # Clear cells
        actions["clear_cells"] = QAction(
            qta.icon("mdi6.delete"), "&Clear Cells", self.view
        )
        actions["clear_cells"].setShortcuts(
            [QKeySequence.Delete, QKeySequence.Backspace]
        )
        actions["clear_cells"].triggered.connect(self.clear_cells)
        return actions

    def sync_visibility_with_actions(self):
        """Sync dock visibility and QAction states in both directions."""
        dock_map = {
            "measurement": self.view.measurement_dock,
            "observable": self.view.observable_dock,
            "parameter": self.view.parameter_dock,
            "condition": self.view.condition_dock,
            "logger": self.view.logger_dock,
            "plot": self.view.plot_dock,
            "visualization": self.view.visualization_dock,
            "simulation": self.view.simulation_dock,
        }

        for key, dock in dock_map.items():
            action = self.actions[f"show_{key}"]

            # Initial sync: block signal to avoid triggering unwanted
            # visibility changes
            was_blocked = action.blockSignals(True)
            action.setChecked(dock.isVisible())
            action.blockSignals(was_blocked)

            # Connect QAction ↔ DockWidget syncing
            action.toggled.connect(dock.setVisible)
            dock.visibilityChanged.connect(action.setChecked)

        # Connect SBML editor visibility toggle
        sbml_action = self.actions["show_sbml_editor"]
        sbml_widget = self.view.sbml_viewer.sbml_widget

        # Store action reference in view for context menus
        self.view.sbml_viewer.sbml_toggle_action = sbml_action
        self.view.sbml_viewer.save_sbml_action = self.actions["save_sbml"]

        # Connect menu action to widget visibility
        sbml_action.toggled.connect(sbml_widget.setVisible)

    def unsaved_changes_change(self, unsaved_changes: bool):
        self.unsaved_changes = unsaved_changes
        if unsaved_changes:
            self.view.setWindowTitle(f"{self.window_title} - Unsaved Changes")
        else:
            self.view.setWindowTitle(self.window_title)

    def maybe_close(self):
        if not self.unsaved_changes:
            self.view.allow_close = True
            return
        reply = QMessageBox.question(
            self.view,
            "Unsaved Changes",
            "You have unsaved changes. Do you want to save them?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Save:
            saved = self.file_io.save_model()
            self.view.allow_close = saved
        elif reply == QMessageBox.Discard:
            self.view.allow_close = True
        else:
            self.view.allow_close = False
        if self.view.allow_close:
            app = QApplication.instance()
            if app and hasattr(self, "_whats_this_filter"):
                app.removeEventFilter(self._whats_this_filter)

    def active_widget(self):
        active_widget = self.view.tab_widget.currentWidget()
        if active_widget == self.view.data_tab:
            active_widget = self.view.data_tab.focusWidget()
        if active_widget and isinstance(active_widget, QTableView):
            return active_widget
        return None

    def active_controller(self):
        active_widget = self.active_widget()
        if active_widget == self.view.measurement_dock.table_view:
            return self.measurement_controller
        if active_widget == self.view.observable_dock.table_view:
            return self.observable_controller
        if active_widget == self.view.parameter_dock.table_view:
            return self.parameter_controller
        if active_widget == self.view.condition_dock.table_view:
            return self.condition_controller
        if active_widget == self.view.visualization_dock.table_view:
            return self.visualization_controller
        if active_widget == self.view.simulation_dock.table_view:
            return self.simulation_controller
        return None

    def delete_rows(self):
        controller = self.active_controller()
        if controller:
            controller.delete_row()

    def add_row(self):
        controller = self.active_controller()
        if controller:
            controller.add_row()

    def add_column(self):
        controller = self.active_controller()
        if controller:
            controller.add_column()

    def delete_column(self):
        controller = self.active_controller()
        if controller:
            controller.delete_column()

    def clear_cells(self):
        controller = self.active_controller()
        if controller:
            controller.clear_cells()

    def filter_table(self):
        """Filter the currently activated tables."""
        filter_text = self.filter_input.text()
        for table_name, tool_button in self.filter_active.items():
            if tool_button.isChecked():
                controller = getattr(self, f"{table_name}_controller")
                controller.filter_table(filter_text)
            else:
                controller = getattr(self, f"{table_name}_controller")
                controller.remove_filter()

    def copy_to_clipboard(self):
        controller = self.active_controller()
        if controller:
            controller.copy_to_clipboard()

    def paste_from_clipboard(self):
        controller = self.active_controller()
        if controller:
            controller.paste_from_clipboard()

    def cut(self):
        controller = self.active_controller()
        if controller:
            controller.copy_to_clipboard()
            controller.clear_cells()

    def open_settings(self):
        """Opens the settings Dialogue."""
        # retrieve all current columns from the tables
        table_columns = {
            "observable": self.observable_controller.get_columns(),
            "parameter": self.parameter_controller.get_columns(),
            "measurement": self.measurement_controller.get_columns(),
            "condition": self.condition_controller.get_columns(),
            "visualization": self.visualization_controller.get_columns(),
            "simulation": self.simulation_controller.get_columns(),
        }
        settings_dialog = SettingsDialog(table_columns, self.view)
        settings_dialog.exec()

    def find(self):
        """Create a find replace bar if it is non existent."""
        if self.view.find_replace_bar is None:
            self.view.create_find_replace_bar(self.find_replace_controller)
        self.view.toggle_find()

    def replace(self):
        """Create a find replace bar if it is non existent."""
        if self.view.find_replace_bar is None:
            self.view.create_find_replace_bar(self.find_replace_controller)
        self.view.toggle_replace()

    def _toggle_whats_this_mode(self, on: bool):
        """
        Enable/disable click-to-help mode.

        On enter: show a short instruction bubble.
        """
        app = QApplication.instance()
        if not app:
            return
        if not on:
            QWhatsThis.hideText()
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass
            app.removeEventFilter(self._whats_this_filter)
            self.logger.log_message("Enden the Help mode.", color="blue")
            return
        # install filter
        app.installEventFilter(self._whats_this_filter)
        QApplication.setOverrideCursor(Qt.WhatsThisCursor)
        self.logger.log_message(
            "Started the Help mode. Click on any widget to see its help.",
            color="blue",
        )
        self._show_help_welcome()

    def _show_help_welcome(self):
        """Welcome with a 'Don't show again' option persisted in QSettings."""
        settings = settings_manager.settings
        if settings.value("help_mode/welcome_disabled", False, type=bool):
            return
        msg = QMessageBox(self.view if hasattr(self, "view") else None)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Help mode")
        msg.setTextFormat(Qt.RichText)
        msg.setText(
            "<b>Welcome to help mode</b><br>"
            "<ul>"
            "<li>Click any widget, tab, or column header to see its "
            "help.</li>"
            "<li>Click the same item again or press <b>Esc</b> to close "
            "the bubble.</li>"
            "<li>Press <b>Esc</b> with no bubble, or toggle the <i>?</i> "
            "button, to exit.</li>"
            "</ul>"
        )
        dont = QCheckBox("Don't show again")
        msg.setCheckBox(dont)
        msg.exec()
        if dont.isChecked():
            settings.setValue("help_mode/welcome_disabled", True)

    def about(self):
        """Show an about dialog."""
        config_file = settings_manager.settings.fileName()
        QMessageBox.about(
            self.view,
            f"About {APP_NAME}",
            f"<b>{APP_NAME}</b><br>"
            f"Version: {version('petab-gui')}<br>"
            f"PEtab version: {version('petab')}<br><br>"
            f"{APP_NAME} is a tool for editing and visualizing PEtab "
            f"problems.<br><br>"
            f"Visit the GitHub repository at "
            f"<a href='{REPO_URL}'>{REPO_URL}</a> "
            "for more information.<br><br>"
            f"<small>Settings are stored in "
            f"<a href='file://{config_file}'>{config_file}</a></small>",
        )

    def _show_next_steps_panel(self):
        """Show the next steps panel."""
        # Sync checkbox state with current settings
        dont_show = settings_manager.get_value(
            "next_steps/dont_show_again", False, bool
        )
        self.next_steps_panel.set_dont_show_again(dont_show)
        self.next_steps_panel.show_panel()

    def _handle_next_steps_dont_show_again(self, dont_show: bool):
        """Handle the 'don't show again' checkbox state change.

        Connected to the next steps panel's dont_show_again_changed signal.
        Persists the user's preference to settings.

        Args:
            dont_show: Whether to suppress the panel on future saves
        """
        settings_manager.set_value("next_steps/dont_show_again", dont_show)
