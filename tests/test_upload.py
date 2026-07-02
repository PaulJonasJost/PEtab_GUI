"""
OLD TESTS.

REMAINING AS TODODS for new refactored app.
Tests for file upload functionality in mother_controller.py.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import yaml

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from petab_gui.controllers.mother_controller import MainController
from petab_gui.models import PEtabModel
from petab_gui.views import MainWindow

# Try to import QApplication for Qt tests
try:
    from PySide6.QtWidgets import QApplication

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False


# Create a module-level QApplication instance if Qt is available
_qapp = None
if _QT_AVAILABLE:
    _qapp = QApplication.instance()
    if _qapp is None:
        _qapp = QApplication([])


class TestYAMLValidation(unittest.TestCase):
    """Test YAML structure validation functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip tests if Qt is not available
        if not _QT_AVAILABLE:
            self.skipTest("Qt not available")

        # Create real application components
        self.view = MainWindow()
        self.model = PEtabModel()
        self.controller = MainController(self.view, self.model)
        self.view.controller = self.controller

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, "view"):
            self.view.close()
            self.view.deleteLater()

    def test_validate_yaml_structure_valid_minimal(self):
        """Test validation with minimal valid YAML structure."""
        yaml_content = {
            "format_version": "1.0",
            "parameter_file": "parameters.tsv",
            "problems": [
                {
                    "sbml_files": ["model.xml"],
                    "measurement_files": ["measurements.tsv"],
                    "observable_files": ["observables.tsv"],
                    "condition_files": ["conditions.tsv"],
                }
            ],
        }

        is_valid, errors = self.controller._validate_yaml_structure(
            yaml_content
        )

        self.assertTrue(is_valid)
        # Should have no critical errors, only potential warnings
        critical_errors = [e for e in errors if "Warning" not in e]
        self.assertEqual(len(critical_errors), 0)

    def test_validate_yaml_structure_missing_format_version(self):
        """Test validation fails when format_version is missing."""
        yaml_content = {
            "parameter_file": "parameters.tsv",
            "problems": [
                {
                    "sbml_files": ["model.xml"],
                    "measurement_files": ["measurements.tsv"],
                    "observable_files": ["observables.tsv"],
                    "condition_files": ["conditions.tsv"],
                }
            ],
        }

        is_valid, errors = self.controller._validate_yaml_structure(
            yaml_content
        )

        self.assertFalse(is_valid)
        self.assertIn("Missing 'format_version' field", errors)

    def test_validate_yaml_structure_missing_problems(self):
        """Test validation fails when problems field is missing."""
        yaml_content = {
            "format_version": "1.0",
            "parameter_file": "parameters.tsv",
        }

        is_valid, errors = self.controller._validate_yaml_structure(
            yaml_content
        )

        self.assertFalse(is_valid)
        self.assertIn("Missing 'problems' field", errors)

    def test_validate_yaml_structure_empty_problems(self):
        """Test validation fails when problems list is empty."""
        yaml_content = {
            "format_version": "1.0",
            "parameter_file": "parameters.tsv",
            "problems": [],
        }

        is_valid, errors = self.controller._validate_yaml_structure(
            yaml_content
        )

        self.assertFalse(is_valid)
        self.assertIn("'problems' must be a non-empty list", errors)

    def test_validate_yaml_structure_missing_sbml_files(self):
        """Test validation fails when sbml_files is missing."""
        yaml_content = {
            "format_version": "1.0",
            "parameter_file": "parameters.tsv",
            "problems": [
                {
                    "measurement_files": ["measurements.tsv"],
                    "observable_files": ["observables.tsv"],
                    "condition_files": ["conditions.tsv"],
                }
            ],
        }

        is_valid, errors = self.controller._validate_yaml_structure(
            yaml_content
        )

        self.assertFalse(is_valid)
        self.assertIn("Problem must contain at least one SBML file", errors)

    def test_validate_yaml_structure_empty_sbml_files(self):
        """Test validation fails when sbml_files is empty."""
        yaml_content = {
            "format_version": "1.0",
            "parameter_file": "parameters.tsv",
            "problems": [
                {
                    "sbml_files": [],
                    "measurement_files": ["measurements.tsv"],
                    "observable_files": ["observables.tsv"],
                    "condition_files": ["conditions.tsv"],
                }
            ],
        }

        is_valid, errors = self.controller._validate_yaml_structure(
            yaml_content
        )

        self.assertFalse(is_valid)
        self.assertIn("Problem must contain at least one SBML file", errors)

    def test_validate_yaml_structure_missing_parameter_file(self):
        """Test validation fails when parameter_file is missing."""
        yaml_content = {
            "format_version": "1.0",
            "problems": [
                {
                    "sbml_files": ["model.xml"],
                    "measurement_files": ["measurements.tsv"],
                    "observable_files": ["observables.tsv"],
                    "condition_files": ["conditions.tsv"],
                }
            ],
        }

        is_valid, errors = self.controller._validate_yaml_structure(
            yaml_content
        )

        self.assertFalse(is_valid)
        self.assertIn("Missing 'parameter_file' at root level", errors)

    def test_validate_yaml_structure_warnings_for_optional_fields(self):
        """Test validation generates warnings for missing optional fields."""
        yaml_content = {
            "format_version": "1.0",
            "problems": [
                {
                    "sbml_files": ["model.xml"],
                    "measurement_files": ["measurements.tsv"],
                    "observable_files": ["observables.tsv"],
                    "condition_files": ["conditions.tsv"],
                }
            ],
        }

        is_valid, errors = self.controller._validate_yaml_structure(
            yaml_content
        )

        # Should be valid despite warnings
        self.assertTrue(is_valid)

        # Should have warnings for missing optional fields
        warnings = [e for e in errors if "Warning" in e]
        self.assertGreater(len(warnings), 0)

        warning_text = " ".join(warnings)
        self.assertIn("visualization_files", warning_text)


class TestFileExistenceValidation(unittest.TestCase):
    """Test file existence validation."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip tests if Qt is not available
        if not _QT_AVAILABLE:
            self.skipTest("Qt not available")

        # Create real application components
        self.view = MainWindow()
        self.model = PEtabModel()
        self.controller = MainController(self.view, self.model)
        self.view.controller = self.controller

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, "view"):
            self.view.close()
            self.view.deleteLater()

    def test_validate_files_exist_all_present(self):
        """Test validation passes when all files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "model.xml").touch()
            (temp_path / "measurements.tsv").touch()
            (temp_path / "observables.tsv").touch()
            (temp_path / "conditions.tsv").touch()
            (temp_path / "parameters.tsv").touch()

            yaml_content = {
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": ["measurements.tsv"],
                        "observable_files": ["observables.tsv"],
                        "condition_files": ["conditions.tsv"],
                    }
                ],
            }

            all_exist, missing = self.controller._validate_files_exist(
                temp_path, yaml_content
            )

            self.assertTrue(all_exist)
            self.assertEqual(len(missing), 0)

    def test_validate_files_exist_missing_sbml(self):
        """Test validation detects missing SBML file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files (except SBML)
            (temp_path / "measurements.tsv").touch()
            (temp_path / "observables.tsv").touch()
            (temp_path / "conditions.tsv").touch()
            (temp_path / "parameters.tsv").touch()

            yaml_content = {
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": ["measurements.tsv"],
                        "observable_files": ["observables.tsv"],
                        "condition_files": ["conditions.tsv"],
                    }
                ],
            }

            all_exist, missing = self.controller._validate_files_exist(
                temp_path, yaml_content
            )

            self.assertFalse(all_exist)
            self.assertIn("model.xml", missing)

    def test_validate_files_exist_missing_multiple(self):
        """Test validation detects multiple missing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create only some test files
            (temp_path / "model.xml").touch()
            (temp_path / "parameters.tsv").touch()

            yaml_content = {
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": ["measurements.tsv"],
                        "observable_files": ["observables.tsv"],
                        "condition_files": ["conditions.tsv"],
                    }
                ],
            }

            all_exist, missing = self.controller._validate_files_exist(
                temp_path, yaml_content
            )

            self.assertFalse(all_exist)
            self.assertIn("measurements.tsv", missing)
            self.assertIn("observables.tsv", missing)
            self.assertIn("conditions.tsv", missing)
            self.assertEqual(len(missing), 3)

    def test_validate_files_exist_multiple_files_per_category(self):
        """Test validation with multiple files per category."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "model.xml").touch()
            (temp_path / "measurements1.tsv").touch()
            (temp_path / "measurements2.tsv").touch()
            (temp_path / "observables1.tsv").touch()
            (temp_path / "observables2.tsv").touch()
            (temp_path / "conditions.tsv").touch()
            (temp_path / "parameters.tsv").touch()

            yaml_content = {
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": [
                            "measurements1.tsv",
                            "measurements2.tsv",
                        ],
                        "observable_files": [
                            "observables1.tsv",
                            "observables2.tsv",
                        ],
                        "condition_files": ["conditions.tsv"],
                    }
                ],
            }

            all_exist, missing = self.controller._validate_files_exist(
                temp_path, yaml_content
            )

            self.assertTrue(all_exist)
            self.assertEqual(len(missing), 0)

    def test_validate_files_exist_missing_one_of_multiple(self):
        """Test validation detects missing file when multiple files listed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files (missing measurements2.tsv)
            (temp_path / "model.xml").touch()
            (temp_path / "measurements1.tsv").touch()
            # measurements2.tsv intentionally not created
            (temp_path / "observables.tsv").touch()
            (temp_path / "conditions.tsv").touch()
            (temp_path / "parameters.tsv").touch()

            yaml_content = {
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": [
                            "measurements1.tsv",
                            "measurements2.tsv",
                        ],
                        "observable_files": ["observables.tsv"],
                        "condition_files": ["conditions.tsv"],
                    }
                ],
            }

            all_exist, missing = self.controller._validate_files_exist(
                temp_path, yaml_content
            )

            self.assertFalse(all_exist)
            self.assertIn("measurements2.tsv", missing)
            self.assertEqual(len(missing), 1)


class TestMultiFileYAMLLoading(unittest.TestCase):
    """Test multi-file YAML loading functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip tests if Qt is not available
        if not _QT_AVAILABLE:
            self.skipTest("Qt not available")

        # Create real application components
        self.view = MainWindow()
        self.model = PEtabModel()
        self.controller = MainController(self.view, self.model)
        self.view.controller = self.controller

        # Add spies to track method calls on real controllers
        self.controller.sbml_controller.overwrite_sbml = Mock(
            wraps=self.controller.sbml_controller.overwrite_sbml
        )
        self.controller.measurement_controller.open_table = Mock(
            wraps=self.controller.measurement_controller.open_table
        )
        self.controller.observable_controller.open_table = Mock(
            wraps=self.controller.observable_controller.open_table
        )
        self.controller.condition_controller.open_table = Mock(
            wraps=self.controller.condition_controller.open_table
        )
        self.controller.parameter_controller.open_table = Mock(
            wraps=self.controller.parameter_controller.open_table
        )

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, "view"):
            self.view.close()
            self.view.deleteLater()

    def test_single_file_yaml_backward_compatibility(self):
        """Test that single-file YAML loading still works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "model.xml").write_text(
                "<?xml version='1.0'?><sbml/>"
            )
            (temp_path / "measurements.tsv").write_text(
                "observableId\ttime\tmeasurement\n"
            )
            (temp_path / "observables.tsv").write_text(
                "observableId\tobservableFormula\n"
            )
            (temp_path / "conditions.tsv").write_text("conditionId\n")
            (temp_path / "parameters.tsv").write_text("parameterId\n")

            # Create YAML file
            yaml_content = {
                "format_version": "1.0",
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": ["measurements.tsv"],
                        "observable_files": ["observables.tsv"],
                        "condition_files": ["conditions.tsv"],
                    }
                ],
            }
            yaml_file = temp_path / "problem.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(yaml_content, f)

            # Mock get_major_version to return 1
            with patch(
                "petab_gui.controllers.mother_controller.get_major_version",
                return_value=1,
            ):
                # Call the method
                self.controller.open_yaml_and_load_files(str(yaml_file))

            # Verify SBML was loaded once
            self.controller.sbml_controller.overwrite_sbml.assert_called_once()

            # Verify each table was loaded once in overwrite mode
            self.controller.measurement_controller.open_table.assert_called_once()
            self.controller.observable_controller.open_table.assert_called_once()
            self.controller.condition_controller.open_table.assert_called_once()
            self.controller.parameter_controller.open_table.assert_called_once()

    def test_multi_file_yaml_loading(self):
        """Test loading YAML with multiple files per category."""
        contr = self.controller.measurement_controller
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "model.xml").write_text(
                "<?xml version='1.0'?><sbml/>"
            )
            (temp_path / "measurements1.tsv").write_text(
                "observableId\ttime\tmeasurement\n"
            )
            (temp_path / "measurements2.tsv").write_text(
                "observableId\ttime\tmeasurement\n"
            )
            (temp_path / "observables1.tsv").write_text(
                "observableId\tobservableFormula\n"
            )
            (temp_path / "observables2.tsv").write_text(
                "observableId\tobservableFormula\n"
            )
            (temp_path / "conditions1.tsv").write_text("conditionId\n")
            (temp_path / "conditions2.tsv").write_text("conditionId\n")
            (temp_path / "parameters.tsv").write_text("parameterId\n")

            # Create YAML file with multiple files per category
            yaml_content = {
                "format_version": "1.0",
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": [
                            "measurements1.tsv",
                            "measurements2.tsv",
                        ],
                        "observable_files": [
                            "observables1.tsv",
                            "observables2.tsv",
                        ],
                        "condition_files": [
                            "conditions1.tsv",
                            "conditions2.tsv",
                        ],
                    }
                ],
            }
            yaml_file = temp_path / "problem.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(yaml_content, f)

            # Mock get_major_version to return 1
            with patch(
                "petab_gui.controllers.mother_controller.get_major_version",
                return_value=1,
            ):
                # Call the method
                self.controller.open_yaml_and_load_files(str(yaml_file))

            # Verify measurement files loading (once in overwrite/append)
            self.assertEqual(contr.open_table.call_count, 2)

            # Check that first call was with mode='overwrite'
            first_call = contr.open_table.call_args_list[0]
            self.assertEqual(first_call[1].get("mode"), "overwrite")

            # Check that second call was with mode='append'
            second_call = contr.open_table.call_args_list[1]
            self.assertEqual(second_call[1].get("mode"), "append")

            # Verify observable files were loaded
            self.assertEqual(
                self.controller.observable_controller.open_table.call_count, 2
            )

            # Verify condition files were loaded
            self.assertEqual(
                self.controller.condition_controller.open_table.call_count, 2
            )


class TestErrorHandling(unittest.TestCase):
    """Test error handling in YAML loading."""

    def setUp(self):
        """Set up test fixtures."""
        # Skip tests if Qt is not available
        if not _QT_AVAILABLE:
            self.skipTest("Qt not available")

        # Create real application components
        self.view = MainWindow()
        self.model = PEtabModel()
        self.controller = MainController(self.view, self.model)
        self.view.controller = self.controller

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, "view"):
            self.view.close()
            self.view.deleteLater()

    def test_invalid_yaml_structure_shows_error(self):
        """Test that invalid YAML structure shows appropriate error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create YAML with invalid structure (missing problems)
            yaml_content = {
                "format_version": "1.0",
                "parameter_file": "parameters.tsv",
            }
            yaml_file = temp_path / "problem.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(yaml_content, f)

            # Mock QMessageBox to capture error display
            with (
                patch(
                    "petab_gui.controllers.mother_controller.QMessageBox"
                ) as mock_msgbox,
                patch(
                    "petab_gui.controllers.mother_controller.get_major_version",
                    return_value=1,
                ),
            ):
                # Call the method
                self.controller.open_yaml_and_load_files(str(yaml_file))

            # Verify error message box was shown
            mock_msgbox.critical.assert_called_once()
            call_args = mock_msgbox.critical.call_args
            self.assertIn("Invalid YAML structure", str(call_args))

    def test_missing_files_shows_error(self):
        """Test that missing files show appropriate error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create YAML but don't create the files it references
            yaml_content = {
                "format_version": "1.0",
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": ["measurements.tsv"],
                        "observable_files": ["observables.tsv"],
                        "condition_files": ["conditions.tsv"],
                    }
                ],
            }
            yaml_file = temp_path / "problem.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(yaml_content, f)

            # Mock QMessageBox to capture error display
            with (
                patch(
                    "petab_gui.controllers.mother_controller.QMessageBox"
                ) as mock_msgbox,
                patch(
                    "petab_gui.controllers.mother_controller.get_major_version",
                    return_value=1,
                ),
            ):
                # Call the method
                self.controller.open_yaml_and_load_files(str(yaml_file))

            # Verify error message box was shown
            mock_msgbox.critical.assert_called_once()
            call_args = mock_msgbox.critical.call_args
            self.assertIn("Missing Files", str(call_args))

    def test_unsupported_petab_version_shows_error(self):
        """Test that unsupported PEtab version shows appropriate error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create valid YAML
            yaml_content = {
                "format_version": "2.0",  # Version 2
                "parameter_file": "parameters.tsv",
                "problems": [
                    {
                        "sbml_files": ["model.xml"],
                        "measurement_files": ["measurements.tsv"],
                        "observable_files": ["observables.tsv"],
                        "condition_files": ["conditions.tsv"],
                    }
                ],
            }
            yaml_file = temp_path / "problem.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(yaml_content, f)

            # Create a spy to track log messages
            logged_messages = []
            original_log = self.controller.logger.log_message

            def log_spy(message, color="black"):
                logged_messages.append(message)
                original_log(message, color)

            self.controller.logger.log_message = log_spy

            # Mock get_major_version to return 2
            with (
                patch(
                    "petab_gui.controllers.mother_controller.get_major_version",
                    return_value=2,
                ),
                patch("petab_gui.controllers.mother_controller.QMessageBox"),
            ):
                self.controller.open_yaml_and_load_files(str(yaml_file))

            # Restore original method
            self.controller.logger.log_message = original_log

            # Check that an error about PEtab version was logged
            version_errors = [
                msg for msg in logged_messages if "PEtab v1" in msg
            ]
            self.assertGreater(len(version_errors), 0)


if __name__ == "__main__":
    unittest.main()
