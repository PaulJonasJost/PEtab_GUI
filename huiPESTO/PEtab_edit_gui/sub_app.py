from PySide6.QtWidgets import QApplication
import sys
import pandas as pd
from .penGUI_view import MainWindow
from .penGUI_model import PandasTableModel
from .penGUI_controller import Controller
from petab.models.sbml_model import SbmlModel
from .C import *

from pathlib import Path

def main():
    app = QApplication([])

    sbml_model = SbmlModel.from_file( Path(__file__).parent / "sbml_model.xml")

    # Load data from TSV files
    dfs = [
        pd.read_csv(Path(__file__).parent / "meas.tsv", sep='\t'),
        pd.read_csv(Path(__file__).parent / "obs.tsv", sep='\t'),
        pd.read_csv(Path(__file__).parent / "para.tsv", sep='\t'),
        pd.read_csv(Path(__file__).parent / "cond.tsv", sep='\t')
    ]

    allowed_columns_list = [MEASUREMENT_COLUMNS, OBSERVABLE_COLUMNS, PARAMETER_COLUMNS, CONDITION_COLUMNS]

    # Create models
    # models = [PandasTableModel(df, allowed_columns) for df, allowed_columns in zip(dfs, allowed_columns_list)]

    # Create the main window
    view = MainWindow()

    # Create the controller
    controller = Controller(view, dfs, sbml_model)

    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
