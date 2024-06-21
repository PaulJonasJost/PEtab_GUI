from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, \
    QTabWidget, QPlainTextEdit, QSplitter, QWidget, QGridLayout, \
    QPushButton, QFrame, QTableView, QHBoxLayout, QMenu, QLabel
import PySide6.QtWidgets as widgets
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QAction, QShortcut, QKeySequence
import sys
from C import CONFIG
from utils import FindReplaceDialog, SyntaxHighlighter
from penGUI_model import SbmlViewerModel


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

        self.grid_layout = QGridLayout()
        self.tables = []
        self.add_row_buttons = []
        self.add_column_buttons = []

        for i in range(4):
            self.create_table_frame(i)

        layout.addLayout(self.grid_layout)

    def create_table_frame(self, index):
        frame = QFrame()
        frame_layout = QVBoxLayout(frame)

        # Add the header label
        table_labels = ["Measurement Table", "Observable Table", "Parameter Table", "Condition Table"]
        label = QLabel(table_labels[index])
        frame_layout.addWidget(label)

        table_view = QTableView()
        table_view.setSortingEnabled(True)
        table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        table_view.customContextMenuRequested.connect(lambda pos, x=index: self.show_context_menu(pos, x))
        self.tables.append(table_view)
        frame_layout.addWidget(table_view)

        button_layout = QHBoxLayout()
        add_row_button = QPushButton("Add Row")
        add_column_button = QPushButton("Add Column")
        self.add_row_buttons.append(add_row_button)
        self.add_column_buttons.append(add_column_button)
        button_layout.addWidget(add_row_button)
        button_layout.addWidget(add_column_button)

        frame_layout.addLayout(button_layout)
        self.grid_layout.addWidget(frame, index // 2, index % 2)

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
