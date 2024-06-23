from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, \
    QTabWidget, QPlainTextEdit, QSplitter, QWidget, QGridLayout, \
    QPushButton, QFrame, QTableView, QHBoxLayout, QMenu, QLabel, \
    QStackedWidget, QToolButton, QStyle
import PySide6.QtWidgets as widgets
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QAction, QShortcut, QKeySequence
import sys
from C import CONFIG
from utils import FindReplaceDialog, SyntaxHighlighter, PlotWidget
from penGUI_model import SbmlViewerModel
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(CONFIG['window_title'])
        self.setGeometry(100, 100, *CONFIG['window_size'])

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("PEtab Editor")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        self.find_replace_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.find_replace_shortcut.activated.connect(self.open_find_replace_dialog)

        self.init_tabs()
        self.init_buttons()

    def init_tabs(self):
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        self.petable_tab = QWidget()
        self.sbml_tab = QWidget()

        self.tabs.addTab(self.petable_tab, "PEtab Tables")
        self.tabs.addTab(self.sbml_tab, "SBML Model")

        self.setup_petable_tab()
        self.setup_sbml_tab()

    def init_buttons(self):
        self.upload_data_matrix_button = QPushButton("Upload Data Matrix")
        self.finish_button = QPushButton("Finish Editing")

        self.main_layout.addWidget(self.upload_data_matrix_button)
        self.main_layout.addWidget(self.finish_button)

    def setup_petable_tab(self):
        layout = QVBoxLayout(self.petable_tab)

        self.grid_layout = QGridLayout()  # Use QGridLayout for 2x2 grid
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

    def create_table_frame(self, index, label_text="", include_stacked_widget=False):
        frame = QFrame()
        frame_layout = QVBoxLayout(frame)

        table_labels = ["Measurement Table", "Observable Table", "Parameter Table", "Condition Table"]

        # Label and button layout
        label_layout = QHBoxLayout()
        label_layout.setContentsMargins(0, 0, 0, 0)
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

        if include_stacked_widget:
            stacked_widget = QStackedWidget()
            stacked_widget.addWidget(table_view)

            plot_frame = QFrame()

            plot_widget = PlotWidget()
            toolbar = NavigationToolbar2QT(plot_widget, self)
            plot_layout = QVBoxLayout()
            plot_layout.addWidget(toolbar)
            plot_layout.addWidget(plot_widget)
            plot_frame.setLayout(plot_layout)
            stacked_widget.addWidget(plot_frame)

            frame_layout.addWidget(stacked_widget)
            self.stacked_widgets.append(stacked_widget)
        else:
            frame_layout.addWidget(table_view)

        button_layout = QHBoxLayout()
        add_row_button = QPushButton("Add Row")
        add_column_button = QPushButton("Add Column")
        self.add_row_buttons.append(add_row_button)
        self.add_column_buttons.append(add_column_button)
        button_layout.addWidget(add_row_button)
        button_layout.addWidget(add_column_button)

        frame_layout.addLayout(button_layout)

        # Add frame to the grid layout
        row = index // 2
        col = index % 2
        self.grid_layout.addWidget(frame, row, col)

        return frame

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
        index = table_view.indexAt(pos)

        if not index.isValid():
            return

        selection_model = table_view.selectionModel()
        selected_indexes = selection_model.selectedIndexes()

        # Create a set of rows that need to be selected
        rows_to_select = set(index.row() for index in selected_indexes)

        # Add the row where the right-click occurred
        rows_to_select.add(index.row())

        # Select all rows that need to be selected
        for row in rows_to_select:
            table_view.selectRow(row)

        context_menu = QMenu(self)
        delete_action = QAction("Delete Row", self)
        delete_action.triggered.connect(lambda: self.controller.delete_row(table_index))
        context_menu.addAction(delete_action)

        context_menu.exec(table_view.viewport().mapToGlobal(pos))

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
        self.sbml_highlighter = SyntaxHighlighter(self.sbml_text_edit.document())
        sbml_layout.addWidget(self.sbml_text_edit)

        # Create Antimony model section
        antimony_layout = QVBoxLayout()
        antimony_label = QLabel("Antimony Model")
        antimony_layout.addWidget(antimony_label)
        self.antimony_text_edit = QPlainTextEdit()
        self.antimony_highlighter = SyntaxHighlighter(self.antimony_text_edit.document())
        antimony_layout.addWidget(self.antimony_text_edit)

        sbml_widget = QWidget()
        sbml_widget.setLayout(sbml_layout)
        antimony_widget = QWidget()
        antimony_widget.setLayout(antimony_layout)

        splitter.addWidget(sbml_widget)
        splitter.addWidget(antimony_widget)
        layout.addWidget(splitter)
    #
    #     self.sbml_text_edit.textChanged.connect(self.on_sbml_text_changed)
    #     self.antimony_text_edit.textChanged.connect(self.on_antimony_text_changed)
    #
    # def on_sbml_text_changed(self):
    #     self.controller.sbml_model.sbml_text = self.sbml_text_edit.toPlainText()
    #
    # def on_antimony_text_changed(self):
    #     self.controller.sbml_model.antimony_text = self.antimony_text_edit.toPlainText()
    #
    # def update_sbml_text(self, text):
    #     self.sbml_text_edit.blockSignals(True)
    #     self.sbml_text_edit.setPlainText(text)
    #     self.sbml_text_edit.blockSignals(False)
    #
    # def update_antimony_text(self, text):
    #     self.antimony_text_edit.blockSignals(True)
    #     self.antimony_text_edit.setPlainText(text)
    #     self.antimony_text_edit.blockSignals(False)
