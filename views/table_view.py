from PySide6.QtWidgets import QDockWidget, QVBoxLayout, QTableView, QPushButton, \
    QHBoxLayout, QWidget
from PySide6.QtCore import Qt

class TableViewer(QDockWidget):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.title = title
        self.setObjectName(title)
        self.setAllowedAreas(
            Qt.AllDockWidgetAreas
        )
        widget = QWidget()
        self.setWidget(widget)
        layout = QVBoxLayout(widget)

        # Create the QTableView for the table content
        self.table_view = QTableView()
        layout.addWidget(self.table_view)

        # # Button panel
        # button_layout = QHBoxLayout()
        # self.add_row_button = QPushButton("Add Row")
        # button_layout.addWidget(self.add_row_button)
        #
        # # Add 'Add Column' button if this is the "Condition Table"
        # if self.title == "Condition Table":
        #     self.add_column_button = QPushButton("Add Column")
        #     button_layout.addWidget(self.add_column_button)
        #
        # layout.addLayout(button_layout)
