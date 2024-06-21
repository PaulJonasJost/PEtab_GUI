from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, \
    QLineEdit, QPushButton, QCompleter
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
import re


class ConditionInputDialog(QDialog):
    def __init__(self, condition_id, condition_columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Condition")

        self.layout = QVBoxLayout(self)

        # Condition ID
        self.condition_id_layout = QHBoxLayout()
        self.condition_id_label = QLabel("Condition ID:", self)
        self.condition_id_input = QLineEdit(self)
        self.condition_id_input.setText(condition_id)
        self.condition_id_input.setReadOnly(True)
        self.condition_id_layout.addWidget(self.condition_id_label)
        self.condition_id_layout.addWidget(self.condition_id_input)
        self.layout.addLayout(self.condition_id_layout)

        # Dynamic fields for existing columns
        self.fields = {}
        for column in condition_columns:
            if column != "conditionId":  # Skip conditionId
                field_layout = QHBoxLayout()
                field_label = QLabel(f"{column}:", self)
                field_input = QLineEdit(self)
                field_layout.addWidget(field_label)
                field_layout.addWidget(field_input)
                self.layout.addLayout(field_layout)
                self.fields[column] = field_input

        # Buttons
        self.buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)
        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.buttons_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_inputs(self):
        inputs = {column: field.text() for column, field in self.fields.items()}
        inputs["conditionId"] = self.condition_id_input.text()
        inputs["conditionName"] = inputs["conditionId"]
        return inputs


class MeasurementInputDialog(QDialog):
    def __init__(self, condition_ids, observable_ids, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Measurement")

        self.layout = QVBoxLayout(self)

        # Observable ID
        self.observable_id_layout = QHBoxLayout()
        self.observable_id_label = QLabel("Observable ID:", self)
        self.observable_id_input = QLineEdit(self)
        self.observable_id_layout.addWidget(self.observable_id_label)
        self.observable_id_layout.addWidget(self.observable_id_input)
        self.layout.addLayout(self.observable_id_layout)

        # Auto-suggestion for Observable ID
        observable_completer = QCompleter(observable_ids, self)
        self.observable_id_input.setCompleter(observable_completer)

        # Measurement
        self.measurement_layout = QHBoxLayout()
        self.measurement_label = QLabel("Measurement:", self)
        self.measurement_input = QLineEdit(self)
        self.measurement_layout.addWidget(self.measurement_label)
        self.measurement_layout.addWidget(self.measurement_input)
        self.layout.addLayout(self.measurement_layout)

        # Timepoints
        self.timepoints_layout = QHBoxLayout()
        self.timepoints_label = QLabel("Timepoints:", self)
        self.timepoints_input = QLineEdit(self)
        self.timepoints_layout.addWidget(self.timepoints_label)
        self.timepoints_layout.addWidget(self.timepoints_input)
        self.layout.addLayout(self.timepoints_layout)

        # Condition ID
        self.condition_id_layout = QHBoxLayout()
        self.condition_id_label = QLabel("Condition ID:", self)
        self.condition_id_input = QLineEdit(self)
        if len(condition_ids) == 1:
            self.condition_id_input.setText(condition_ids[0])
        self.condition_id_layout.addWidget(self.condition_id_label)
        self.condition_id_layout.addWidget(self.condition_id_input)
        self.layout.addLayout(self.condition_id_layout)

        # Auto-suggestion for Condition ID
        condition_completer = QCompleter(condition_ids, self)
        self.condition_id_input.setCompleter(condition_completer)

        # Buttons
        self.buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)
        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.buttons_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_inputs(self):
        return (self.observable_id_input.text(),
                self.measurement_input.text(),
                self.timepoints_input.text(),
                self.condition_id_input.text())


class ObservableInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Observable")

        self.layout = QVBoxLayout(self)

        # Observable ID
        self.observable_id_layout = QHBoxLayout()
        self.observable_id_label = QLabel("Observable ID:", self)
        self.observable_id_input = QLineEdit(self)
        self.observable_id_layout.addWidget(self.observable_id_label)
        self.observable_id_layout.addWidget(self.observable_id_input)
        self.layout.addLayout(self.observable_id_layout)

        # Observable Formula
        self.observable_formula_layout = QHBoxLayout()
        self.observable_formula_label = QLabel("Observable Formula:", self)
        self.observable_formula_input = QLineEdit(self)
        self.observable_formula_layout.addWidget(self.observable_formula_label)
        self.observable_formula_layout.addWidget(self.observable_formula_input)
        self.layout.addLayout(self.observable_formula_layout)

        # Buttons
        self.buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)
        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.buttons_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_inputs(self):
        return self.observable_id_input.text(), self.observable_formula_input.text()


class ObservableFormulaInputDialog(QDialog):
    def __init__(self, observable_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            "You added a new observable! Please provide the formula."
        )

        self.layout = QVBoxLayout(self)

        # Observable ID
        self.observable_id_layout = QHBoxLayout()
        self.observable_id_label = QLabel("Observable ID:", self)
        self.observable_id_input = QLineEdit(self)
        self.observable_id_input.setText(observable_id)
        self.observable_id_input.setReadOnly(True)
        self.observable_id_layout.addWidget(self.observable_id_label)
        self.observable_id_layout.addWidget(self.observable_id_input)
        self.layout.addLayout(self.observable_id_layout)

        # Observable Formula
        self.observable_formula_layout = QHBoxLayout()
        self.observable_formula_label = QLabel("Observable Formula:", self)
        self.observable_formula_input = QLineEdit(self)
        self.observable_formula_layout.addWidget(self.observable_formula_label)
        self.observable_formula_layout.addWidget(self.observable_formula_input)
        self.layout.addLayout(self.observable_formula_layout)

        # Buttons
        self.buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)
        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.buttons_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_inputs(self):
        return (self.observable_id_input.text(),
                self.observable_formula_input.text())


class ParameterInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Parameter")

        self.layout = QVBoxLayout(self)

        # Parameter ID
        self.parameter_id_layout = QHBoxLayout()
        self.parameter_id_label = QLabel("Parameter ID:", self)
        self.parameter_id_input = QLineEdit(self)
        self.parameter_id_layout.addWidget(self.parameter_id_label)
        self.parameter_id_layout.addWidget(self.parameter_id_input)
        self.layout.addLayout(self.parameter_id_layout)

        # Nominal Value
        self.nominal_value_layout = QHBoxLayout()
        self.nominal_value_label = QLabel("Nominal Value (optional):", self)
        self.nominal_value_input = QLineEdit(self)
        self.nominal_value_layout.addWidget(self.nominal_value_label)
        self.nominal_value_layout.addWidget(self.nominal_value_input)
        self.layout.addLayout(self.nominal_value_layout)

        # Buttons
        self.buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK", self)
        self.cancel_button = QPushButton("Cancel", self)
        self.buttons_layout.addWidget(self.ok_button)
        self.buttons_layout.addWidget(self.cancel_button)
        self.layout.addLayout(self.buttons_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_inputs(self):
        return self.parameter_id_input.text(), self.nominal_value_input.text()


def set_dtypes(data_frame, columns, index_columns=None):
    dtype_mapping = {
        "STRING": str,
        "NUMERIC": float,
        "BOOLEAN": bool
    }
    for column, dtype in columns.items():
        if column in data_frame.columns:
            data_frame[column] = data_frame[column].astype(dtype_mapping[dtype])
    if index_columns:
        data_frame.set_index(index_columns, inplace=True)
    return data_frame


class FindReplaceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find and Replace")

        self.find_label = QLabel("Find:")
        self.find_input = QLineEdit()

        self.replace_label = QLabel("Replace:")
        self.replace_input = QLineEdit()

        self.find_button = QPushButton("Find")
        self.replace_button = QPushButton("Replace")
        self.close_button = QPushButton("Close")

        # self.find_button.clicked.connect(self.find)
        self.replace_button.clicked.connect(self.replace)
        self.close_button.clicked.connect(self.close)

        layout = QVBoxLayout()
        form_layout = QHBoxLayout()
        form_layout.addWidget(self.find_label)
        form_layout.addWidget(self.find_input)
        form_layout.addWidget(self.replace_label)
        form_layout.addWidget(self.replace_input)

        layout.addLayout(form_layout)
        # layout.addWidget(self.find_button)
        layout.addWidget(self.replace_button)
        layout.addWidget(self.close_button)
        self.setLayout(layout)

    # def find(self):
    #     find_text = self.find_input.text()
    #     self.parent().controller.find_text(find_text)

    def replace(self):
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        self.parent().controller.replace_text(find_text, replace_text)


class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []

        # Define formats
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("blue"))

        # Define regex patterns
        keywords = ["keyword1", "keyword2"]  # Replace with actual keywords
        keyword_pattern = r"\b(" + "|".join(keywords) + r")\b"
        self._rules.append((re.compile(keyword_pattern), keyword_format))

    def highlightBlock(self, text):
        for pattern, format in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)

