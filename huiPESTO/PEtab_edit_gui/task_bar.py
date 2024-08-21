from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction


class TaskBar:
    def __init__(self, parent):
        # Create the menu bar
        self.menu_bar = parent.menuBar()

        # Create and add menus to the menu bar
        self.file_menu = QMenu("File", parent)
        self.edit_menu = QMenu("Edit", parent)

        self.menu_bar.addMenu(self.file_menu)
        self.menu_bar.addMenu(self.edit_menu)

        # Create actions for the File menu
        self.open_action = QAction("Open", parent)
        self.save_action = QAction("Save", parent)
        self.exit_action = QAction("Save and Close", parent)

        # Create the Upload Table submenu
        self.upload_table_menu = QMenu("Upload Tables or SBML", parent)
        self.file_menu.addMenu(self.upload_table_menu)

        # Add actions for each table in the Upload Table submenu
        self.upload_measurement_table_action = QAction(
            "Upload Measurement Table", parent
        )
        self.upload_observable_table_action = QAction(
            "Upload Observable Table", parent
        )
        self.upload_parameter_table_action = QAction(
            "Upload Parameter Table", parent
        )
        self.upload_condition_table_action = QAction(
            "Upload Condition Table", parent
        )
        self.upload_sbml_action = QAction("Upload SBML", parent)

        self.upload_table_menu.addAction(self.upload_measurement_table_action)
        self.upload_table_menu.addAction(self.upload_observable_table_action)
        self.upload_table_menu.addAction(self.upload_parameter_table_action)
        self.upload_table_menu.addAction(self.upload_condition_table_action)
        self.upload_table_menu.addAction(self.upload_sbml_action)

        # Add actions to the File menu
        self.file_menu.addAction(self.open_action)
        self.file_menu.addAction(self.save_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

        # Create actions for the Edit menu
        self.find_replace_action = QAction("Find/Replace", parent)
        self.delete_action = QAction("Delete Rows", parent)

        # Add actions to the Edit menu
        self.edit_menu.addAction(self.find_replace_action)
        self.edit_menu.addAction(self.delete_action)
