from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, \
    QLineEdit, QPushButton, QCompleter, QCheckBox, QGridLayout
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
import re
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class ConditionInputDialog(QDialog):
    def __init__(self, condition_id, condition_columns, initial_values=None, error_key=None, parent=None):
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
                if initial_values and column in initial_values:
                    field_input.setText(str(initial_values[column]))
                    if column == error_key:
                        field_input.setStyleSheet("background-color: red;")
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
    def __init__(
        self,
        condition_ids = None,
        observable_ids = None,
        initial_values=None,
        error_key=None,
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Add Measurement")

        self.layout = QVBoxLayout(self)

        # Observable ID
        self.observable_id_layout = QHBoxLayout()
        self.observable_id_label = QLabel("Observable ID:", self)
        self.observable_id_input = QLineEdit(self)
        if initial_values and "observableId" in initial_values:
            self.observable_id_input.setText(str(initial_values["observableId"]))
            if "observableId" == error_key:
                self.observable_id_input.setStyleSheet("background-color: red;")
        self.observable_id_layout.addWidget(self.observable_id_label)
        self.observable_id_layout.addWidget(self.observable_id_input)
        self.layout.addLayout(self.observable_id_layout)

        if observable_ids:
            # Auto-suggestion for Observable ID
            observable_completer = QCompleter(observable_ids, self)
            self.observable_id_input.setCompleter(observable_completer)

        # Measurement
        self.measurement_layout = QHBoxLayout()
        self.measurement_label = QLabel("Measurement:", self)
        self.measurement_input = QLineEdit(self)
        if initial_values and "measurement" in initial_values:
            self.measurement_input.setText(str(initial_values["measurement"]))
            if "measurement" == error_key:
                self.measurement_input.setStyleSheet("background-color: red;")
        self.measurement_layout.addWidget(self.measurement_label)
        self.measurement_layout.addWidget(self.measurement_input)
        self.layout.addLayout(self.measurement_layout)

        # Timepoints
        self.timepoints_layout = QHBoxLayout()
        self.timepoints_label = QLabel("Timepoints:", self)
        self.timepoints_input = QLineEdit(self)
        if initial_values and "time" in initial_values:
            self.timepoints_input.setText(str(initial_values["time"]))
            if "time" == error_key:
                self.timepoints_input.setStyleSheet("background-color: red;")
        self.timepoints_layout.addWidget(self.timepoints_label)
        self.timepoints_layout.addWidget(self.timepoints_input)
        self.layout.addLayout(self.timepoints_layout)

        # Condition ID
        self.condition_id_layout = QHBoxLayout()
        self.condition_id_label = QLabel("Condition ID:", self)
        self.condition_id_input = QLineEdit(self)
        if initial_values and "conditionId" in initial_values:
            self.condition_id_input.setText(str(initial_values["conditionId"]))
            if "conditionId" == error_key:
                self.condition_id_input.setStyleSheet("background-color: red;")
        elif condition_ids and len(condition_ids) == 1:
            self.condition_id_input.setText(condition_ids[0])
        self.condition_id_layout.addWidget(self.condition_id_label)
        self.condition_id_layout.addWidget(self.condition_id_input)
        self.layout.addLayout(self.condition_id_layout)

        if condition_ids:
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
    def __init__(self, initial_values=None, error_key=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Observable")

        self.layout = QVBoxLayout(self)

        # Observable ID
        self.observable_id_layout = QHBoxLayout()
        self.observable_id_label = QLabel("Observable ID:", self)
        self.observable_id_input = QLineEdit(self)
        if initial_values and "observableId" in initial_values:
            self.observable_id_input.setText(str(initial_values["observableId"]))
            if "observableId" == error_key:
                self.observable_id_input.setStyleSheet("background-color: red;")
        self.observable_id_layout.addWidget(self.observable_id_label)
        self.observable_id_layout.addWidget(self.observable_id_input)
        self.layout.addLayout(self.observable_id_layout)

        # Observable Formula
        self.observable_formula_layout = QHBoxLayout()
        self.observable_formula_label = QLabel("Observable Formula:", self)
        self.observable_formula_input = QLineEdit(self)
        if initial_values and "observableFormula" in initial_values:
            self.observable_formula_input.setText(str(initial_values["observableFormula"]))
            if "observableFormula" == error_key:
                self.observable_formula_input.setStyleSheet("background-color: red;")
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
    def __init__(self, initial_values=None, error_key=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Parameter")

        self.layout = QVBoxLayout(self)

        # Parameter ID
        self.parameter_id_layout = QHBoxLayout()
        self.parameter_id_label = QLabel("Parameter ID:", self)
        self.parameter_id_input = QLineEdit(self)
        if initial_values and "parameterId" in initial_values:
            self.parameter_id_input.setText(str(initial_values["parameterId"]))
            if "parameterId" == error_key:
                self.parameter_id_input.setStyleSheet("background-color: red;")
        self.parameter_id_layout.addWidget(self.parameter_id_label)
        self.parameter_id_layout.addWidget(self.parameter_id_input)
        self.layout.addLayout(self.parameter_id_layout)

        # Nominal Value
        self.nominal_value_layout = QHBoxLayout()
        self.nominal_value_label = QLabel("Nominal Value (optional):", self)
        self.nominal_value_input = QLineEdit(self)
        if initial_values and "nominalValue" in initial_values:
            self.nominal_value_input.setText(str(initial_values["nominalValue"]))
            if "nominalValue" == error_key:
                self.nominal_value_input.setStyleSheet("background-color: red;")
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
    def __init__(self, parent=None, mode="petab", checkbox_states=None):
        super().__init__(parent)
        self.setWindowTitle("Find and Replace")
        self.mode = mode
        self.checkbox_states = checkbox_states or {}

        self.find_label = QLabel("Find:")
        self.find_input = QLineEdit()

        self.replace_label = QLabel("Replace:")
        self.replace_input = QLineEdit()

        self.find_button = QPushButton("Find")
        self.replace_button = QPushButton("Replace")
        self.close_button = QPushButton("Close")

        self.replace_button.clicked.connect(self.replace)
        self.close_button.clicked.connect(self.close)

        layout = QVBoxLayout()
        form_layout = QHBoxLayout()
        form_layout.addWidget(self.find_label)
        form_layout.addWidget(self.find_input)
        form_layout.addWidget(self.replace_label)
        form_layout.addWidget(self.replace_input)

        layout.addLayout(form_layout)

        checkbox_layout = QGridLayout()

        if self.mode == "petab":
            self.measurement_checkbox = QCheckBox("Measurement Table")
            self.observable_checkbox = QCheckBox("Observable Table")
            self.parameter_checkbox = QCheckBox("Parameter Table")
            self.condition_checkbox = QCheckBox("Condition Table")

            checkbox_layout.addWidget(self.measurement_checkbox, 0, 0)
            checkbox_layout.addWidget(self.observable_checkbox, 0, 1)
            checkbox_layout.addWidget(self.parameter_checkbox, 1, 0)
            checkbox_layout.addWidget(self.condition_checkbox, 1, 1)

            self.measurement_checkbox.setChecked(self.checkbox_states.get("measurement", False))
            self.observable_checkbox.setChecked(self.checkbox_states.get("observable", False))
            self.parameter_checkbox.setChecked(self.checkbox_states.get("parameter", False))
            self.condition_checkbox.setChecked(self.checkbox_states.get("condition", False))
        else:  # SBML mode
            self.sbml_checkbox = QCheckBox("SBML Text")
            self.antimony_checkbox = QCheckBox("Antimony Text")

            checkbox_layout.addWidget(self.sbml_checkbox, 0, 0)
            checkbox_layout.addWidget(self.antimony_checkbox, 0, 1)

            self.sbml_checkbox.setChecked(self.checkbox_states.get("sbml", False))
            self.antimony_checkbox.setChecked(self.checkbox_states.get("antimony", False))

        layout.addLayout(checkbox_layout)

        layout.addWidget(self.replace_button)
        layout.addWidget(self.close_button)
        self.setLayout(layout)

    def closeEvent(self, event):
        if self.mode == "petab":
            self.checkbox_states["measurement"] = self.measurement_checkbox.isChecked()
            self.checkbox_states["observable"] = self.observable_checkbox.isChecked()
            self.checkbox_states["parameter"] = self.parameter_checkbox.isChecked()
            self.checkbox_states["condition"] = self.condition_checkbox.isChecked()
        else:  # SBML mode
            self.checkbox_states["sbml"] = self.sbml_checkbox.isChecked()
            self.checkbox_states["antimony"] = self.antimony_checkbox.isChecked()
        super().closeEvent(event)

    def replace(self):
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()

        if self.mode == "petab":
            selected_models = []
            if self.measurement_checkbox.isChecked():
                selected_models.append(0)
            if self.observable_checkbox.isChecked():
                selected_models.append(1)
            if self.parameter_checkbox.isChecked():
                selected_models.append(2)
            if self.condition_checkbox.isChecked():
                selected_models.append(3)

            self.parent().controller.replace_text(find_text, replace_text, selected_models)
        else:  # SBML mode
            if self.sbml_checkbox.isChecked():
                sbml_text = self.parent().sbml_text_edit.toPlainText()
                sbml_text = sbml_text.replace(find_text, replace_text)
                self.parent().sbml_text_edit.setPlainText(sbml_text)

            if self.antimony_checkbox.isChecked():
                antimony_text = self.parent().antimony_text_edit.toPlainText()
                antimony_text = antimony_text.replace(find_text, replace_text)
                self.parent().antimony_text_edit.setPlainText(antimony_text)




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


def validate_value(value, expected_type):
    try:
        if expected_type == "STRING":
            value = str(value)
        elif expected_type == "NUMERIC":
            value = float(value)
        elif expected_type == "BOOLEAN":
            value = bool(value)
    except ValueError as e:
        return None, str(e)
    return value, None


class PlotWidget(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(PlotWidget, self).__init__(fig)
