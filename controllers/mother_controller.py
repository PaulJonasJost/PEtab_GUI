from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtGui import QShortcut, QKeySequence
import zipfile
import tempfile
import os
from io import BytesIO
import yaml
from ..utils import FindReplaceDialog
from PySide6.QtCore import Qt
from pathlib import Path
from ..models import PEtabModel
from .sbml_controller import SbmlController
from .table_controllers import MeasurementController, ObservableController, \
    ConditionController, ParameterController
from .logger_controller import LoggerController


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
        self.view = view
        self.model = model
        self.task_bar = view.task_bar
        self.logger = LoggerController(view.logger_views)
        # CONTROLERS
        self.measurement_controller = MeasurementController(
            self.view.measurement_dock,
            self.model.measurement,
            self.logger,
            self
        )
        self.observable_controller = ObservableController(
            self.view.observable_dock,
            self.model.observable,
            self.logger,
            self
        )
        self.parameter_controller = ParameterController(
            self.view.parameter_dock,
            self.model.parameter,
            self.logger,
            self
        )
        self.condition_controller = ConditionController(
            self.view.condition_dock,
            self.model.condition,
            self.logger,
            self
        )
        self.sbml_controller = SbmlController(
            self.view.sbml_viewer,
            self.model.sbml,
            self.logger,
            self
        )
        # Checkbox states for Find + Replace
        self.petab_checkbox_states = {
            "measurement": False,
            "observable": False,
            "parameter": False,
            "condition": False
        }
        self.sbml_checkbox_states = {
            "sbml": False,
            "antimony": False
        }
        self.unsaved_changes = False
        # SHORTCUTS
        self.shortcuts = {
            "find+replace": QShortcut(QKeySequence("Ctrl+R"), self.view),
            "save": QShortcut(QKeySequence("Ctrl+S"), self.view),
        }

        self.setup_connections()
        self.setup_shortcuts()
        self.setup_edit_menu()
        self.setup_file_menu()
        self.setup_view_menu()


    def setup_shortcuts(self):
        """Create shortcuts for the main window."""
        self.shortcuts["find+replace"].activated.connect(
            self.open_find_replace_dialog
        )
        self.shortcuts["save"].activated.connect(
            self.save_model
        )

    # CONNECTIONS
    def setup_edit_menu(self):
        """Create connections for the Edit menu actions in task bar."""
        edit_menu = self.task_bar.edit_menu
        # Find and Replace
        edit_menu.find_replace_action.triggered.connect(
            self.open_find_replace_dialog
        )
        # Delete Rows
        edit_menu.delete_action.triggered.connect(
            lambda: self.delete_row(table_index=None)
        )
        # Add columns
        edit_menu.add_c_meas_action.triggered.connect(
            self.measurement_controller.add_column
        )
        edit_menu.add_c_obs_action.triggered.connect(
            self.observable_controller.add_column
        )
        edit_menu.add_c_para_action.triggered.connect(
            self.parameter_controller.add_column
        )
        edit_menu.add_c_cond_action.triggered.connect(
            self.condition_controller.add_column
        )
        # TODO: rework dialogs?
        # # Add rows
        # task_bar.add_r_meas_action.triggered.connect(
        #     lambda: self.add_row(0)
        # )
        # task_bar.add_r_obs_action.triggered.connect(
        #     lambda: self.add_row(1)
        # )
        # task_bar.add_r_para_action.triggered.connect(
        #     lambda: self.add_row(2)
        # )
        # task_bar.add_r_cond_action.triggered.connect(
        #     lambda: self.add_row(3)
        # )

    def setup_file_menu(self):
        """Create connections for the File menu actions in task bar."""
        file_menu = self.task_bar.file_menu
        # Upload different tables
        file_menu.upload_measurement_table_action.triggered.connect(
            self.measurement_controller.upload_and_overwrite_table
        )
        file_menu.upload_observable_table_action.triggered.connect(
            self.observable_controller.upload_and_overwrite_table
        )
        file_menu.upload_parameter_table_action.triggered.connect(
            self.parameter_controller.upload_and_overwrite_table
        )
        file_menu.upload_condition_table_action.triggered.connect(
            self.condition_controller.upload_and_overwrite_table
        )
        file_menu.upload_sbml_action.triggered.connect(
            self.sbml_controller.upload_and_overwrite_sbml
        )
        # upload yaml
        file_menu.upload_yaml_action.triggered.connect(
            self.upload_yaml_and_load_files
        )
        # Save
        file_menu.save_action.triggered.connect(
            self.save_model
        )
        # Close
        file_menu.exit_action.triggered.connect(
            self.view.close
        )

    def setup_view_menu(self):
        """Create connections for the View menu actions in task bar."""
        view_menu = self.task_bar.view_menu
        # Add actions to the menu for re-adding tables
        view_menu.show_measurement.toggled.connect(
            lambda checked: self.view.measurement_dock.setVisible(checked)
        )
        view_menu.show_observable.toggled.connect(
            lambda checked: self.view.observable_dock.setVisible(checked)
        )
        view_menu.show_parameter.toggled.connect(
            lambda checked: self.view.parameter_dock.setVisible(checked)
        )
        view_menu.show_condition.toggled.connect(
            lambda checked: self.view.condition_dock.setVisible(checked)
        )
        view_menu.show_logger.toggled.connect(
            lambda checked: self.view.logger_dock.setVisible(checked)
        )
        view_menu.show_plot.toggled.connect(
            lambda checked: self.view.plot_dock.setVisible(checked)
        )


    def setup_connections(self):
        """Setup connections.

        Sets all connections that communicate from one different
        Models/Views/Controllers to another. Also sets general connections.
        """
        # Rename Observable
        self.observable_controller.observable_2be_renamed.connect(
            self.measurement_controller.rename_observable
        )
        # Add new observable
        self.model.measurement.observable_id_changed.connect(
            self.observable_controller.maybe_add_observable
        )
        # Maybe Move to a Plot Model
        self.view.measurement_dock.table_view.selectionModel().selectionChanged.connect(
            self.handle_selection_changed
        )
        self.model.measurement.dataChanged.connect(
            self.handle_data_changed
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
        self.model.sbml.something_changed.connect(
            self.unsaved_changes_change
        )
        # Closing event
        self.view.closing_signal.connect(
            self.maybe_close
        )

    def save_model(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(
            self.view,
            "Save Project",
            "",
            "Zip Files (*.zip)",
            options=options
        )
        if not file_name:
            return None
        if not file_name.endswith(".zip"):
            file_name += ".zip"

        # Create a temporary directory to save the model's files
        with tempfile.TemporaryDirectory() as temp_dir:
            self.model.save(temp_dir)

            # Create a bytes buffer to hold the zip file in memory
            buffer = BytesIO()
            with zipfile.ZipFile(buffer, 'w') as zip_file:
                # Add files to zip archive
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        with open(file_path, 'rb') as f:
                            zip_file.writestr(file, f.read())
            with open(file_name, 'wb') as f:
                f.write(buffer.getvalue())

        QMessageBox.information(
            self.view, "Save Project",
            f"Project saved successfully to {file_name}"
        )

    def open_find_replace_dialog(self):
        current_tab = self.view.tabs.currentIndex()
        if current_tab == 0:
            # TODO: rewrite functionality in FindReplaceDialoge
            dialog = FindReplaceDialog(
                self.view, mode="petab",
                checkbox_states=self.petab_checkbox_states
            )
        elif current_tab == 1:
            dialog = FindReplaceDialog(
                self.view, mode="sbml",
                checkbox_states=self.sbml_checkbox_states
            )
        dialog.exec()

    def handle_selection_changed(self):
        # ??
        self.update_plot()

    def handle_data_changed(self, top_left, bottom_right, roles):
        # ??
        if not roles or Qt.DisplayRole in roles:
            self.update_plot()

    def update_plot(self):
        # ??
        selection_model = \
            self.view.measurement_dock.table_view.selectionModel()
        indexes = selection_model.selectedIndexes()
        if not indexes:
            return None

        selected_points = {}
        for index in indexes:
            if index.row() == self.model.measurement.get_df().shape[0]:
                continue
            row = index.row()
            observable_id = self.model.measurement._data_frame.iloc[row][
                "observableId"]
            if observable_id not in selected_points:
                selected_points[observable_id] = []
            selected_points[observable_id].append({
                "x": self.model.measurement._data_frame.iloc[row]["time"],
                "y": self.model.measurement._data_frame.iloc[row]["measurement"]
            })
        if selected_points == {}:
            return None

        measurement_data = self.model.measurement._data_frame
        plot_data = {
            "all_data": [],
            "selected_points": selected_points
        }
        for observable_id in selected_points.keys():
            observable_data = measurement_data[
                measurement_data["observableId"] == observable_id]
            plot_data["all_data"].append({
                "observable_id": observable_id,
                "x": observable_data["time"].tolist(),
                "y": observable_data["measurement"].tolist()
            })

        self.view.plot_dock.update_visualization(plot_data)

    def upload_yaml_and_load_files(self):
        """Upload files from a YAML configuration.

        Opens a dialog to upload yaml file. Creates a PEtab problem and
        overwrites the current PEtab model with the new problem.
        """
        yaml_path, _ = QFileDialog.getOpenFileName(
            self.view,
            "Open YAML File",
            "",
            "YAML Files (*.yaml *.yml)"
        )
        if not yaml_path:
            return
        try:
            # Load the YAML content
            with open(yaml_path, 'r') as file:
                yaml_content = yaml.safe_load(file)

            # Resolve the directory of the YAML file to handle relative paths
            yaml_dir = Path(yaml_path).parent

            # Upload SBML model
            sbml_file_path = \
                yaml_dir / yaml_content['problems'][0]['sbml_files'][0]
            self.sbml_controller.upload_and_overwrite_sbml(sbml_file_path)
            self.measurement_controller.upload_and_overwrite_table(
                yaml_dir / yaml_content['problems'][0]['measurement_files'][0]
            )
            self.observable_controller.upload_and_overwrite_table(
                yaml_dir / yaml_content['problems'][0]['observable_files'][0]
            )
            self.parameter_controller.upload_and_overwrite_table(
                yaml_dir / yaml_content['parameter_file']
            )
            self.condition_controller.upload_and_overwrite_table(
                yaml_dir / yaml_content['problems'][0]['condition_files'][0]
            )
            self.logger.log_message(
                "All files uploaded successfully from the YAML configuration.",
                color="green"
            )
            self.unsaved_changes = False

        except Exception as e:
            self.logger.log_message(
                f"Failed to upload files from YAML: {str(e)}", color="red"
            )

    def unsaved_changes_change(self, unsaved_changes: bool):
        self.unsaved_changes = unsaved_changes
        if unsaved_changes:
            self.view.setWindowTitle("PEtab Editor - Unsaved Changes")
        else:
            self.view.setWindowTitle("PEtab Editor")

    def maybe_close(self):
        if not self.unsaved_changes:
            self.view.allow_close = True
            return
        reply = QMessageBox.question(
            self.view, "Unsaved Changes",
            "You have unsaved changes. Do you want to save them?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )
        if reply == QMessageBox.Save:
            self.save_model()
            self.view.allow_close = True
        elif reply == QMessageBox.Discard:
            self.view.allow_close = True
        else:
            self.view.allow_close = False

