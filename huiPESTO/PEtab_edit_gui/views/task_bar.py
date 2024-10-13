from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction


class BasicMenu:
    """Base class for a TaskBar Menu."""
    def __init__(self, parent):
        self.menu = QMenu(self.menu_name(), parent)
        self.parent = parent

    def add_action_or_menu(
        self, name: str, menu: QMenu = None, is_action: bool = True
    ):
        """Add an action or a menu to the menu.

        If no menu is provided, the action is added to the main menu."""
        if menu is None:
            menu = self.menu
        if is_action:
            action = QAction(name, self.parent)
            menu.addAction(action)
        else:
            action = QMenu(name, self.parent)
            menu.addMenu(action)
        return action

    def add_checkable_action(self, name: str, menu: QMenu = None):
        """Add a checkable action to the menu."""
        action = self.add_action_or_menu(name, menu)
        action.setCheckable(True)
        action.setChecked(True)
        return action

    def menu_name(self):
        """This method should be overridden to provide the menu's name."""
        raise NotImplementedError("Subclasses must provide a menu name.")



class FileMenu(BasicMenu):
    """Class for the file menu."""
    def menu_name(self):
        return "File"
    def __init__(self, parent):
        super().__init__(parent)

        # Open, Save, and Close actions
        self.upload_yaml_action = self.add_action_or_menu(
            "Upload YAML Configuration"
        )
        self.upload_table_menu = self.add_action_or_menu(
            "Upload Tables or SBML", is_action=False
        )
        self.upload_measurement_table_action = self.add_action_or_menu(
            "Upload Measurement Table", self.upload_table_menu
        )
        self.upload_observable_table_action = self.add_action_or_menu(
            "Upload Observable Table", self.upload_table_menu
        )
        self.upload_parameter_table_action = self.add_action_or_menu(
            "Upload Parameter Table", self.upload_table_menu
        )
        self.upload_condition_table_action = self.add_action_or_menu(
            "Upload Condition Table", self.upload_table_menu
        )
        self.upload_sbml_action = self.add_action_or_menu(
            "Upload SBML", self.upload_table_menu
        )


        # self.open_action = self.add_action("Open")  # Currently no Function?
        self.save_action = self.add_action_or_menu("Save")
        self.menu.addSeparator()
        self.exit_action = self.add_action_or_menu("Close")


class EditMenu(BasicMenu):
    """Edit Menu of the TaskBar."""
    def menu_name(self):
        return "Edit"

    def __init__(self, parent):
        super().__init__(parent)

        # Find and Replace
        self.find_replace_action = self.add_action_or_menu("Find/Replace")
        # Delete Rows
        self.delete_action = self.add_action_or_menu("Delete Rows")
        # Add Columns submenu
        self.add_column_menu = self.add_action_or_menu(
            "Add Column to ...", is_action=False
        )
        self.add_c_meas_action = self.add_action_or_menu(
            "... Measurement Table", self.add_column_menu
        )
        self.add_c_obs_action = self.add_action_or_menu(
            "... Observable Table", self.add_column_menu
        )
        self.add_c_para_action = self.add_action_or_menu(
            "... Parameter Table", self.add_column_menu
        )
        self.add_c_cond_action = self.add_action_or_menu(
            "... Condition Table", self.add_column_menu
        )
        # Add Rows submenu
        self.add_row_menu = self.add_action_or_menu(
            "Add Row to ...", is_action=False
        )
        self.add_r_meas_action = self.add_action_or_menu(
            "... Measurement Table", self.add_row_menu
        )
        self.add_r_obs_action = self.add_action_or_menu(
            "... Observable Table", self.add_row_menu
        )
        self.add_r_para_action = self.add_action_or_menu(
            "... Parameter Table", self.add_row_menu
        )
        self.add_r_cond_action = self.add_action_or_menu(
            "... Condition Table", self.add_row_menu
        )


class ViewMenu(BasicMenu):
    """View Menu of the TaskBar."""
    def menu_name(self):
        return "View"

    def __init__(self, parent):
        super().__init__(parent)

        # Add actions to the menu for re-adding tables
        self.show_measurement = self.add_checkable_action("Measurement Table")
        self.show_observable = self.add_checkable_action("Observable Table")
        self.show_parameter = self.add_checkable_action("Parameter Table")
        self.show_condition = self.add_checkable_action("Condition Table")
        self.show_logger = self.add_checkable_action("Info")
        self.show_plot = self.add_checkable_action("Data Plot")


class TaskBar:
    """TaskBar of the PEtab Editor."""
    def add_menu(self, menu_class):
        """Add a menu to the task bar."""
        menu = menu_class(self.parent)
        self.menu.addMenu(menu.menu)
        return menu

    def __init__(self, parent):
        self.parent = parent
        self.menu = parent.menuBar()
        self.file_menu = self.add_menu(FileMenu)
        self.edit_menu = self.add_menu(EditMenu)
        self.view_menu = self.add_menu(ViewMenu)
