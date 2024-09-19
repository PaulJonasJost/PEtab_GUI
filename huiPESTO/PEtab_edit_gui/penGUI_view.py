from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, \
    QTabWidget, QPlainTextEdit, QSplitter, QWidget, QGridLayout, \
    QPushButton, QFrame, QTableView, QHBoxLayout, QMenu, QLabel, \
    QStackedWidget, QToolButton, QStyle, QAbstractItemView, QTextBrowser, QMessageBox
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QAction, QShortcut, QKeySequence, QCursor
import sys
from .C import CONFIG
from .utils import FindReplaceDialog, SyntaxHighlighter, PlotWidget
from .penGUI_model import SbmlViewerModel
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
import matplotlib.pyplot as plt
from .task_bar import TaskBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(CONFIG['window_title'])
        self.setGeometry(100, 100, *CONFIG['window_size'])

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.splitter = QSplitter(Qt.Vertical, central_widget)

        # Initialize tabs and buttons
        self.task_bar = TaskBar(self)
        self.init_tabs()
        self.init_buttons()

        # Add the tabs and the button/info box layout to the splitter
        self.splitter.addWidget(self.tabs)  # The tabs go on top
        self.splitter.addWidget(
            self.button_info_widget
        )  # The buttons/info box goes below

        # Set the initial size ratio
        self.splitter.setStretchFactor(0, 8)
        self.splitter.setStretchFactor(1, 2)

        # Set the splitter as the main layout of the central widget
        main_layout = QVBoxLayout(central_widget)
        main_layout.addWidget(self.splitter)

        # Set the handle width to make it easier to grab and adjust
        self.splitter.setHandleWidth(5)

    def init_tabs(self):
        self.tabs = QTabWidget()

        self.petable_tab = QWidget()
        self.sbml_tab = QWidget()

        self.tabs.addTab(self.petable_tab, "PEtab Tables")
        self.tabs.addTab(self.sbml_tab, "SBML Model")

        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.setup_petable_tab()
        self.setup_sbml_tab()

    def init_buttons(self):
        self.upload_data_matrix_button = QPushButton("Upload Data Matrix")
        self.reset_to_original_button = QPushButton("Reset to Original Model")
        self.finish_button = QPushButton("Finish Editing")
        self.reset_to_original_button.hide()
        button_size = self.reset_to_original_button.sizeHint()
        self.finish_button.setMinimumSize(button_size)
        self.upload_data_matrix_button.setMinimumSize(button_size)
        self.reset_to_original_button.setMinimumSize(button_size)

        self.logger = QTextBrowser()
        button_layout = QVBoxLayout()

        button_layout.addWidget(self.upload_data_matrix_button)
        button_layout.addWidget(self.reset_to_original_button)
        button_layout.addWidget(self.finish_button)

        # Combine the button layout and logger into a single widget
        self.button_info_widget = QWidget()
        layout = QHBoxLayout(self.button_info_widget)
        layout.addLayout(button_layout)
        layout.addWidget(self.logger)

    def on_tab_changed(self, index):
        if index == 0:  # PEtab Tables tab
            self.upload_data_matrix_button.show()
            self.reset_to_original_button.hide()
        elif index == 1:  # SBML Model tab
            self.upload_data_matrix_button.hide()
            self.reset_to_original_button.show()

    def setup_petable_tab(self):
        layout = QVBoxLayout(self.petable_tab)

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(0)
        layout.addLayout(self.grid_layout)

        self.tables = []
        self.add_row_buttons = []
        self.add_column_buttons = []
        self.stacked_widgets = []

        for i in range(3):
            self.create_table_frame(i)

        self.create_table_frame(3, "Condition Table", include_stacked_widget=True)

        # Set stretch factors for equal space allocation
        for i in range(2):
            self.grid_layout.setRowStretch(i, 1)
            self.grid_layout.setColumnStretch(i, 1)

    def get_current_table_index(self):
        # Choose the table that has focus and has a selection (blue highlight)
        for index, table_view in enumerate(self.tables):
            if table_view.hasFocus() and table_view.selectionModel().hasSelection():
                return index
        self.controller.log_message(
            "No table was found active.",
            color="orange"
        )
        return None

    def create_table_frame(self, index, label_text="", include_stacked_widget=False):
        frame = QFrame()
        frame_layout = QVBoxLayout(frame)
        if include_stacked_widget:
            frame_layout.setContentsMargins(0, 0, 0, 0)
        else:    
            frame_layout.setContentsMargins(9, 9, 9, 9)

        table_labels = ["Measurement Table", "Observable Table", "Parameter Table", "Condition Table"]

        # Label and button layout
        label_layout = QHBoxLayout()
        label_layout.setContentsMargins(9 if include_stacked_widget else 0, 0, 0, 0)
        label = QLabel(label_text if label_text else table_labels[index])
        label_layout.addWidget(label)

        if include_stacked_widget:
            toggle_button = QToolButton()
            toggle_button.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_DialogResetButton')))
            toggle_button.setStyleSheet("QToolButton { padding: 0px; margin: 0px; }")  # Remove padding and margin
            toggle_button.clicked.connect(lambda: self.toggle_view(stacked_widget, label, toggle_button))
            label_layout.addWidget(toggle_button)

        frame_layout.addLayout(label_layout)

        table_view = QTableView()
        table_view.setSortingEnabled(True)
        table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        table_view.customContextMenuRequested.connect(lambda pos, x=index: self.show_context_menu(pos, x))
        self.tables.append(table_view)

        button_layout = QHBoxLayout()
        add_row_button = QPushButton("Add Row")
        add_column_button = QPushButton("Add Column")
        self.add_row_buttons.append(add_row_button)
        self.add_column_buttons.append(add_column_button)
        button_layout.addWidget(add_row_button)
        button_layout.addWidget(add_column_button)

        if include_stacked_widget:
            stacked_widget = QStackedWidget()
            table_frame = QFrame()
            table_frame.setFrameShape(QFrame.NoFrame)
            table_frame.setContentsMargins(0, 0, 0, 0)
            table_frame_layout = QVBoxLayout(table_frame)
            table_frame_layout.addWidget(table_view)
            table_frame_layout.addLayout(button_layout)
            stacked_widget.addWidget(table_frame)

            plot_frame = QFrame()

            self.plot_widget = PlotWidget()
            toolbar = NavigationToolbar2QT(self.plot_widget, self)
            plot_layout = QVBoxLayout()
            plot_layout.addWidget(toolbar)
            plot_layout.addWidget(self.plot_widget)
            plot_frame.setLayout(plot_layout)
            stacked_widget.addWidget(plot_frame)

            frame_layout.addWidget(stacked_widget)
            self.stacked_widgets.append(stacked_widget)
        else:
            frame_layout.addWidget(table_view)
            frame_layout.addLayout(button_layout)

        # Add frame to the grid layout
        row = index // 2
        col = index % 2
        self.grid_layout.addWidget(frame, row, col)

        return frame

    def update_visualization(self, plot_data=None):
        self.plot_widget.axes.cla()
        color_map = plt.get_cmap(
            "tab10")  # Using a colormap with distinct colors
        handles = []  # List to store handles for legend
        labels = []  # List to store labels for legend

        # Plot all data points with lower alpha for unselected points
        for idx, data in enumerate(plot_data["all_data"]):
            color = color_map(idx)
            handle, = self.plot_widget.axes.plot(data["x"], data["y"], 'o--',
                                                 color=color, alpha=0.5,
                                                 label=data["observable_id"])
            handles.append(handle)
            labels.append(data["observable_id"])

        # Plot selected points with full alpha
        for idx, (observable_id, points) in enumerate(
                plot_data["selected_points"].items()):
            color = color_map(idx)
            selected_x = [point["x"] for point in points]
            selected_y = [point["y"] for point in points]
            selected_handle, = self.plot_widget.axes.plot(selected_x,
                                                          selected_y, 'o',
                                                          color=color, alpha=1,
                                                          label=f"{observable_id} (selected)")
            handles.append(selected_handle)
            labels.append(f"{observable_id} (selected)")

        # Add legend
        self.plot_widget.axes.legend(handles=handles, labels=labels)
        self.plot_widget.draw()

    def toggle_view(self, stacked_widget, label, toggle_button):
        current_index = stacked_widget.currentIndex()
        new_index = 1 if current_index == 0 else 0
        stacked_widget.setCurrentIndex(new_index)

        if new_index == 1:
            label.setText("Data Plot")
            toggle_button.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_FileDialogContentsView')))
        else:
            label.setText("Condition Table")
            toggle_button.setIcon(self.style().standardIcon(getattr(QStyle, 'SP_DialogResetButton')))

    def show_context_menu(self, pos, table_index):
        table_view = self.tables[table_index]
        # Ensure that the selection mode is set to multi-selection
        table_view.setSelectionMode(QAbstractItemView.MultiSelection)
        table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        original_selection_mode = table_view.selectionMode()
        original_selection_behavior = table_view.selectionBehavior()

        index = table_view.indexAt(pos)

        if not index.isValid():
            return

        selection_model = table_view.selectionModel()
        selected_indexes = selection_model.selectedIndexes()

        # Create a set of rows that need to be selected
        rows_to_select = set(index.row() for index in selected_indexes)

        # Add the row where the right-click occurred
        rows_to_select.add(index.row())

        context_menu = QMenu(self)
        delete_action = QAction("Delete Row", self)
        delete_action.triggered.connect(
            lambda: self.controller.delete_row(table_index, rows_to_select)
        )
        context_menu.addAction(delete_action)

        context_menu.exec(table_view.viewport().mapToGlobal(pos))
        table_view.setSelectionMode(original_selection_mode)
        table_view.setSelectionBehavior(original_selection_behavior)

    def open_find_replace_dialog(self):
        dialog = FindReplaceDialog(self)
        dialog.exec()

    def setup_sbml_tab(self):
        layout = QVBoxLayout(self.sbml_tab)

        splitter = QSplitter(Qt.Horizontal)

        # Create SBML model section
        sbml_layout = QVBoxLayout()
        sbml_label = QLabel("SBML Model")
        sbml_layout.addWidget(sbml_label)
        self.sbml_text_edit = QPlainTextEdit()
        self.sbml_highlighter = SyntaxHighlighter(
            self.sbml_text_edit.document())
        sbml_layout.addWidget(self.sbml_text_edit)

        # Add forward changes button for SBML
        self.forward_sbml_button = QPushButton("Forward Changes to Antimony")
        sbml_layout.addWidget(self.forward_sbml_button)

        # Create Antimony model section
        antimony_layout = QVBoxLayout()
        antimony_label = QLabel("Antimony Model")
        antimony_layout.addWidget(antimony_label)
        self.antimony_text_edit = QPlainTextEdit()
        self.antimony_highlighter = SyntaxHighlighter(
            self.antimony_text_edit.document())
        antimony_layout.addWidget(self.antimony_text_edit)

        # Add forward changes button for Antimony
        self.forward_antimony_button = QPushButton("Forward Changes to SBML")
        antimony_layout.addWidget(self.forward_antimony_button)

        sbml_widget = QWidget()
        sbml_widget.setLayout(sbml_layout)
        antimony_widget = QWidget()
        antimony_widget.setLayout(antimony_layout)

        splitter.addWidget(sbml_widget)
        splitter.addWidget(antimony_widget)
        layout.addWidget(splitter)

    def closeEvent(self, event):
        if self.controller.unsaved_changes:
            # Show a message box asking whether to save unsaved changes
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )

            if reply == QMessageBox.Save:
                self.controller.save_model()
                event.accept()  # Close the window after saving
            elif reply == QMessageBox.Discard:
                event.accept()  # Close the window without saving
            else:
                event.ignore()  # Do not close the window
        else:
            # No unsaved changes, proceed with closing
            event.accept()
