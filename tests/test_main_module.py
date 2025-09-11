"""
Tests for the __main__.py module.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import src.subtranslate.__main__ as main_module


class TestMainModule(unittest.TestCase):
    """Tests for the __main__.py module."""

    def test_main_version(self):
        """Test main function with --version argument."""
        with patch("sys.argv", ["subtranslate", "--version"]), patch(
            "builtins.print"
        ) as mock_print:

            result = main_module.main()

        self.assertEqual(result, 0)
        mock_print.assert_called_once()
        # Should print version information
        printed_text = mock_print.call_args[0][0]
        self.assertIn("SubtranSlate v", printed_text)

    def test_main_help_default(self):
        """Test main function with no arguments (should show help)."""
        with patch("sys.argv", ["subtranslate"]):
            # This should show help and exit
            with self.assertRaises(SystemExit):
                main_module.main()

    @patch("src.subtranslate.__main__.cli_main")
    def test_main_with_args(self, mock_cli_main):
        """Test main function with arguments passed to CLI."""
        mock_cli_main.return_value = 0

        with patch("sys.argv", ["subtranslate", "input.srt", "output.srt"]):
            result = main_module.main()

        self.assertEqual(result, 0)
        mock_cli_main.assert_called_once_with(["input.srt", "output.srt"])

    @patch("src.subtranslate.__main__.cli_main")
    def test_main_with_translate_command(self, mock_cli_main):
        """Test main function with translate command."""
        mock_cli_main.return_value = 0

        with patch("sys.argv", ["subtranslate", "translate", "input.srt", "output.srt"]):
            result = main_module.main()

        self.assertEqual(result, 0)
        mock_cli_main.assert_called_once_with(["translate", "input.srt", "output.srt"])

    @patch("src.subtranslate.__main__.cli_main")
    def test_main_cli_error(self, mock_cli_main):
        """Test main function when CLI returns error."""
        mock_cli_main.return_value = 1

        with patch("sys.argv", ["subtranslate", "input.srt", "output.srt"]):
            result = main_module.main()

        self.assertEqual(result, 1)

    def test_main_called_as_script(self):
        """Test that main is called when module is run as script."""
        with patch("src.subtranslate.__main__.main") as mock_main, patch("sys.exit") as mock_exit:

            mock_main.return_value = 42

            # Simulate __name__ == '__main__'
            with patch.object(main_module, "__name__", "__main__"):
                exec(
                    compile("if __name__ == '__main__': sys.exit(main())", "<string>", "exec"),
                    main_module.__dict__,
                )

            mock_main.assert_called_once()
            mock_exit.assert_called_once_with(42)

    def test_parse_args_remainder(self):
        """Test argument parsing with remainder arguments."""
        test_args = ["translate", "input.srt", "output.srt", "--verbose"]

        with patch("argparse.ArgumentParser.parse_args") as mock_parse:
            mock_args = Mock()
            mock_args.version = False
            mock_args.remainder = test_args
            mock_parse.return_value = mock_args

            with patch("src.subtranslate.__main__.cli_main") as mock_cli_main:
                mock_cli_main.return_value = 0

                result = main_module.main()

        mock_cli_main.assert_called_once_with(test_args)

    def test_import_version(self):
        """Test that version is imported correctly."""
        # Test that the version import works
        from src.subtranslate import __version__

        self.assertIsInstance(__version__, str)
        self.assertRegex(__version__, r"\d+\.\d+\.\d+")


if __name__ == "__main__":
    unittest.main()
