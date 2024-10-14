from PySide6.QtWidgets import QApplication
import sys
import petab.v1 as petab

from .views import MainWindow
from .controllers import MainController
from .models import PEtabModel

from pathlib import Path

def find_example(path: Path) -> Path:
    while path.parent != path:
        if (path / "example").is_dir():
            return path / "example"
        path = path.parent
        
    raise FileNotFoundError("Could not find examples directory")

def main():
    app = QApplication([])

    petab_problem = petab.Problem.from_yaml(
        find_example(Path(__file__).parent) / "problem.yaml"
    )
    model = PEtabModel(petab_problem)
    view = MainWindow()
    MainController(view, model)

    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
