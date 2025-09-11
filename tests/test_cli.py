"""
Tests for the CLI functionality.
"""

import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.subtranslate.cli import handle_encoding_command, handle_translate_command, main, parse_args
from src.subtranslate.core.subtitle import SubtitleError
from src.subtranslate.core.translation import RateLimitError, TranslationError


class TestParseArgs(unittest.TestCase):
    """Tests for argument parsing."""

    def test_parse_args_default_translate(self):
        """Test parsing arguments with default translate command."""
        args = parse_args(["input.srt", "output.srt"])

        self.assertEqual(args.command, "translate")
        self.assertEqual(args.input, "input.srt")
        self.assertEqual(args.output, "output.srt")
        self.assertEqual(args.src_lang, "en")
        self.assertEqual(args.target_lang, "zh-CN")

    def test_parse_args_explicit_translate(self):
        """Test parsing arguments with explicit translate command."""
        args = parse_args(["translate", "input.srt", "output.srt", "-s", "fr", "-t", "de"])

        self.assertEqual(args.command, "translate")
        self.assertEqual(args.input, "input.srt")
        self.assertEqual(args.output, "output.srt")
        self.assertEqual(args.src_lang, "fr")
        self.assertEqual(args.target_lang, "de")

    def test_parse_args_translate_options(self):
        """Test parsing translate command with all options."""
        args = parse_args(
            [
                "translate",
                "input.srt",
                "output.srt",
                "--src-lang",
                "en",
                "--target-lang",
                "es",
                "--mode",
                "naive",
                "--only-translation",
                "--space",
                "--encoding",
                "UTF-16",
                "--batch",
                "--pattern",
                "*.sub",
                "--api-key",
                "test_key",
                "--service",
                "google",
                "--verbose",
                "--no-resume",
            ]
        )

        self.assertEqual(args.command, "translate")
        self.assertEqual(args.mode, "naive")
        self.assertFalse(args.both)  # --only-translation sets both to False
        self.assertTrue(args.space)
        self.assertEqual(args.encoding, "UTF-16")
        self.assertTrue(args.batch)
        self.assertEqual(args.pattern, "*.sub")
        self.assertEqual(args.api_key, "test_key")
        self.assertEqual(args.service, "google")
        self.assertTrue(args.verbose)
        self.assertTrue(args.no_resume)

    def test_parse_args_encode_command(self):
        """Test parsing encode command."""
        args = parse_args(["encode", "input.srt", "-t", "utf-8,tis-620"])

        self.assertEqual(args.command, "encode")
        self.assertEqual(args.input, "input.srt")
        self.assertEqual(args.to_encoding, "utf-8,tis-620")

    def test_parse_args_encode_list_encodings(self):
        """Test parsing encode command with --list-encodings."""
        args = parse_args(["encode", "--list-encodings"])

        self.assertEqual(args.command, "encode")
        self.assertTrue(args.list_encodings)

    def test_parse_args_encode_options(self):
        """Test parsing encode command with all options."""
        args = parse_args(
            [
                "encode",
                "input.srt",
                "--output-dir",
                "/tmp",
                "--from-encoding",
                "utf-8",
                "--to-encoding",
                "tis-620,cp874",
                "--all",
                "--recommended",
                "--language",
                "th",
                "--batch",
                "--pattern",
                "*.srt",
                "--verbose",
            ]
        )

        self.assertEqual(args.command, "encode")
        self.assertEqual(args.input, "input.srt")
        self.assertEqual(args.output_dir, "/tmp")
        self.assertEqual(args.from_encoding, "utf-8")
        self.assertEqual(args.to_encoding, "tis-620,cp874")
        self.assertTrue(args.all)
        self.assertTrue(args.recommended)
        self.assertEqual(args.language, "th")
        self.assertTrue(args.batch)
        self.assertEqual(args.pattern, "*.srt")
        self.assertTrue(args.verbose)

    def test_parse_args_encode_missing_input(self):
        """Test parsing encode command without input raises error."""
        with self.assertRaises(SystemExit):
            parse_args(["encode"])

    def test_parse_args_encode_list_encodings_no_input_required(self):
        """Test that --list-encodings doesn't require input."""
        args = parse_args(["encode", "--list-encodings"])

        self.assertEqual(args.command, "encode")
        self.assertTrue(args.list_encodings)
        # Input should be None when just listing encodings
        self.assertIsNone(args.input)


class TestHandleEncodingCommand(unittest.TestCase):
    """Tests for handle_encoding_command function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    @patch("src.subtranslate.cli.COMMON_ENCODINGS", ["utf-8", "tis-620", "cp874"])
    def test_handle_encoding_list_encodings(self):
        """Test listing encodings."""
        args = argparse.Namespace(list_encodings=True, verbose=False)

        with patch("builtins.print") as mock_print:
            result = handle_encoding_command(args)

        self.assertEqual(result, 0)
        # Should print header and encodings
        mock_print.assert_any_call("Supported encodings:")
        mock_print.assert_any_call("  utf-8")
        mock_print.assert_any_call("  tis-620")
        mock_print.assert_any_call("  cp874")

    @patch("src.subtranslate.cli.convert_subtitle_encoding")
    @patch("src.subtranslate.cli.detect_encoding")
    @patch("os.path.isfile")
    def test_handle_encoding_single_file(self, mock_isfile, mock_detect, mock_convert):
        """Test encoding conversion for single file."""
        mock_isfile.return_value = True
        mock_detect.return_value = "utf-8"
        mock_convert.return_value = True

        args = argparse.Namespace(
            list_encodings=False,
            input="test.srt",
            output_dir=None,
            from_encoding=None,
            to_encoding="tis-620",
            all=False,
            recommended=False,
            language="en",
            batch=False,
            pattern="*.srt",
            verbose=False,
        )

        result = handle_encoding_command(args)

        self.assertEqual(result, 0)
        mock_detect.assert_called_once_with("test.srt")
        mock_convert.assert_called_once()

    @patch("src.subtranslate.cli.convert_subtitle_encoding")
    @patch("src.subtranslate.cli.detect_encoding")
    @patch("os.path.isfile")
    def test_handle_encoding_single_file_multiple_encodings(
        self, mock_isfile, mock_detect, mock_convert
    ):
        """Test encoding conversion for single file to multiple encodings."""
        mock_isfile.return_value = True
        mock_detect.return_value = "utf-8"
        mock_convert.return_value = True

        args = argparse.Namespace(
            list_encodings=False,
            input="test.srt",
            output_dir=None,
            from_encoding=None,
            to_encoding="tis-620,cp874",
            all=False,
            recommended=False,
            language="en",
            batch=False,
            pattern="*.srt",
            verbose=False,
        )

        result = handle_encoding_command(args)

        self.assertEqual(result, 0)
        # Should convert to both encodings
        self.assertEqual(mock_convert.call_count, 2)

    @patch("src.subtranslate.cli.get_recommended_encodings")
    @patch("src.subtranslate.cli.convert_subtitle_encoding")
    @patch("src.subtranslate.cli.detect_encoding")
    @patch("os.path.isfile")
    def test_handle_encoding_recommended(
        self, mock_isfile, mock_detect, mock_convert, mock_recommended
    ):
        """Test encoding conversion with recommended encodings."""
        mock_isfile.return_value = True
        mock_detect.return_value = "utf-8"
        mock_convert.return_value = True
        mock_recommended.return_value = ["tis-620", "cp874"]

        args = argparse.Namespace(
            list_encodings=False,
            input="test.srt",
            output_dir=None,
            from_encoding=None,
            to_encoding=None,
            all=False,
            recommended=True,
            language="th",
            batch=False,
            pattern="*.srt",
            verbose=False,
        )

        result = handle_encoding_command(args)

        self.assertEqual(result, 0)
        mock_recommended.assert_called_once_with("th")
        self.assertEqual(mock_convert.call_count, 2)

    @patch("src.subtranslate.cli.COMMON_ENCODINGS", ["utf-8", "tis-620"])
    @patch("src.subtranslate.cli.convert_subtitle_encoding")
    @patch("src.subtranslate.cli.detect_encoding")
    @patch("os.path.isfile")
    def test_handle_encoding_all(self, mock_isfile, mock_detect, mock_convert):
        """Test encoding conversion to all encodings."""
        mock_isfile.return_value = True
        mock_detect.return_value = "utf-8"
        mock_convert.return_value = True

        args = argparse.Namespace(
            list_encodings=False,
            input="test.srt",
            output_dir=None,
            from_encoding=None,
            to_encoding=None,
            all=True,
            recommended=False,
            language="en",
            batch=False,
            pattern="*.srt",
            verbose=False,
        )

        result = handle_encoding_command(args)

        self.assertEqual(result, 0)
        self.assertEqual(mock_convert.call_count, 2)

    @patch("os.path.isfile")
    def test_handle_encoding_file_not_found(self, mock_isfile):
        """Test handling non-existent file."""
        mock_isfile.return_value = False

        args = argparse.Namespace(
            list_encodings=False,
            input="nonexistent.srt",
            output_dir=None,
            from_encoding=None,
            to_encoding="tis-620",
            all=False,
            recommended=False,
            language="en",
            batch=False,
            pattern="*.srt",
            verbose=False,
        )

        result = handle_encoding_command(args)

        self.assertEqual(result, 1)

    @patch("src.subtranslate.cli.convert_to_multiple_encodings")
    @patch("glob.glob")
    @patch("os.path.isdir")
    def test_handle_encoding_batch(self, mock_isdir, mock_glob, mock_convert_multiple):
        """Test batch encoding conversion."""
        mock_isdir.return_value = True
        mock_glob.return_value = ["file1.srt", "file2.srt"]
        mock_convert_multiple.return_value = {"utf-8": True, "tis-620": True}

        args = argparse.Namespace(
            list_encodings=False,
            input=self.temp_dir.name,
            output_dir=None,
            from_encoding=None,
            to_encoding="utf-8,tis-620",
            all=False,
            recommended=False,
            language="en",
            batch=True,
            pattern="*.srt",
            verbose=False,
        )

        result = handle_encoding_command(args)

        self.assertEqual(result, 0)
        # Should convert multiple files
        self.assertEqual(mock_convert_multiple.call_count, 2)

    @patch("glob.glob")
    @patch("os.path.isdir")
    def test_handle_encoding_batch_no_files(self, mock_isdir, mock_glob):
        """Test batch encoding with no matching files."""
        mock_isdir.return_value = True
        mock_glob.return_value = []

        args = argparse.Namespace(
            list_encodings=False,
            input=self.temp_dir.name,
            output_dir=None,
            from_encoding=None,
            to_encoding="tis-620",
            all=False,
            recommended=False,
            language="en",
            batch=True,
            pattern="*.srt",
            verbose=False,
        )

        result = handle_encoding_command(args)

        self.assertEqual(result, 1)

    @patch("os.path.isdir")
    def test_handle_encoding_batch_not_directory(self, mock_isdir):
        """Test batch encoding with non-directory input."""
        mock_isdir.return_value = False

        args = argparse.Namespace(
            list_encodings=False,
            input="notadirectory",
            output_dir=None,
            from_encoding=None,
            to_encoding="tis-620",
            all=False,
            recommended=False,
            language="en",
            batch=True,
            pattern="*.srt",
            verbose=False,
        )

        result = handle_encoding_command(args)

        self.assertEqual(result, 1)


class TestHandleTranslateCommand(unittest.TestCase):
    """Tests for handle_translate_command function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    @patch("src.subtranslate.cli.SubtitleTranslator")
    @patch("os.path.isfile")
    def test_handle_translate_single_file(self, mock_isfile, mock_translator_class):
        """Test translating a single file."""
        mock_isfile.return_value = True
        mock_translator = Mock()
        mock_translator_class.return_value = mock_translator

        args = argparse.Namespace(
            input="input.srt",
            output="output.srt",
            src_lang="en",
            target_lang="es",
            mode="split",
            both=True,
            space=False,
            encoding="UTF-8",
            batch=False,
            pattern="*.srt",
            api_key="test_key",
            service="google",
            verbose=False,
            no_resume=False,
        )

        result = handle_translate_command(args)

        self.assertEqual(result, 0)
        mock_translator_class.assert_called_once_with(
            translation_service="google", api_key="test_key"
        )
        mock_translator.translate_file.assert_called_once()

    @patch("src.subtranslate.cli.SubtitleTranslator")
    @patch("os.path.isfile")
    def test_handle_translate_single_file_not_found(self, mock_isfile, mock_translator_class):
        """Test translating non-existent file."""
        mock_isfile.return_value = False

        args = argparse.Namespace(
            input="nonexistent.srt",
            output="output.srt",
            src_lang="en",
            target_lang="es",
            mode="split",
            both=True,
            space=False,
            encoding="UTF-8",
            batch=False,
            pattern="*.srt",
            api_key=None,
            service="google",
            verbose=False,
            no_resume=False,
        )

        result = handle_translate_command(args)

        self.assertEqual(result, 1)

    @patch("src.subtranslate.cli.SubtitleTranslator")
    @patch("os.path.isdir")
    def test_handle_translate_batch(self, mock_isdir, mock_translator_class):
        """Test batch translation."""
        mock_isdir.return_value = True
        mock_translator = Mock()
        mock_translator_class.return_value = mock_translator
        mock_translator.batch_translate_directory.return_value = {
            "file1.srt": {"status": "success"},
            "file2.srt": {"status": "success"},
        }

        args = argparse.Namespace(
            input=self.temp_dir.name,
            output=self.temp_dir.name + "_out",
            src_lang="en",
            target_lang="es",
            mode="split",
            both=True,
            space=False,
            encoding="UTF-8",
            batch=True,
            pattern="*.srt",
            api_key=None,
            service="google",
            verbose=False,
            no_resume=False,
        )

        result = handle_translate_command(args)

        self.assertEqual(result, 0)
        mock_translator.batch_translate_directory.assert_called_once()

    @patch("src.subtranslate.cli.SubtitleTranslator")
    @patch("os.path.isdir")
    def test_handle_translate_batch_no_success(self, mock_isdir, mock_translator_class):
        """Test batch translation with no successful files."""
        mock_isdir.return_value = True
        mock_translator = Mock()
        mock_translator_class.return_value = mock_translator
        mock_translator.batch_translate_directory.return_value = {
            "file1.srt": {"status": "error"},
            "file2.srt": {"status": "rate_limited"},
        }

        args = argparse.Namespace(
            input=self.temp_dir.name,
            output=self.temp_dir.name + "_out",
            src_lang="en",
            target_lang="es",
            mode="split",
            both=True,
            space=False,
            encoding="UTF-8",
            batch=True,
            pattern="*.srt",
            api_key=None,
            service="google",
            verbose=False,
            no_resume=False,
        )

        result = handle_translate_command(args)

        self.assertEqual(result, 1)

    @patch("os.path.isdir")
    def test_handle_translate_batch_not_directory(self, mock_isdir):
        """Test batch translation with non-directory input."""
        mock_isdir.return_value = False

        args = argparse.Namespace(
            input="notadirectory",
            output="output",
            src_lang="en",
            target_lang="es",
            mode="split",
            both=True,
            space=False,
            encoding="UTF-8",
            batch=True,
            pattern="*.srt",
            api_key=None,
            service="google",
            verbose=False,
            no_resume=False,
        )

        result = handle_translate_command(args)

        self.assertEqual(result, 1)

    def test_handle_translate_space_language_detection(self):
        """Test automatic space detection for different target languages."""
        space_languages = ["fr", "en", "de", "es", "it", "pt", "ru"]

        for lang in space_languages:
            with patch("src.subtranslate.cli.SubtitleTranslator") as mock_translator_class, patch(
                "os.path.isfile", return_value=True
            ):

                mock_translator = Mock()
                mock_translator_class.return_value = mock_translator

                args = argparse.Namespace(
                    input="input.srt",
                    output="output.srt",
                    src_lang="en",
                    target_lang=lang,
                    mode="split",
                    both=True,
                    space=False,  # Should be overridden
                    encoding="UTF-8",
                    batch=False,
                    pattern="*.srt",
                    api_key=None,
                    service="google",
                    verbose=False,
                    no_resume=False,
                )

                handle_translate_command(args)

                # Check that space=True was passed for this language
                call_args = mock_translator.translate_file.call_args
                self.assertTrue(call_args[1]["space"])


class TestMain(unittest.TestCase):
    """Tests for the main function."""

    def test_main_translate_command(self):
        """Test main function with translate command."""
        with patch("src.subtranslate.cli.handle_translate_command") as mock_handle:
            mock_handle.return_value = 0

            result = main(["translate", "input.srt", "output.srt"])

        self.assertEqual(result, 0)
        mock_handle.assert_called_once()

    def test_main_encode_command(self):
        """Test main function with encode command."""
        with patch("src.subtranslate.cli.handle_encoding_command") as mock_handle:
            mock_handle.return_value = 0

            result = main(["encode", "input.srt"])

        self.assertEqual(result, 0)
        mock_handle.assert_called_once()

    def test_main_default_args(self):
        """Test main function with default arguments (no command specified)."""
        with patch("src.subtranslate.cli.handle_translate_command") as mock_handle:
            mock_handle.return_value = 0

            result = main(["input.srt", "output.srt"])

        self.assertEqual(result, 0)
        mock_handle.assert_called_once()

    def test_main_subtitle_error(self):
        """Test main function handling SubtitleError."""
        with patch("src.subtranslate.cli.handle_translate_command") as mock_handle:
            mock_handle.side_effect = SubtitleError("Subtitle error")

            result = main(["input.srt", "output.srt"])

        self.assertEqual(result, 1)

    def test_main_translation_error(self):
        """Test main function handling TranslationError."""
        with patch("src.subtranslate.cli.handle_translate_command") as mock_handle:
            mock_handle.side_effect = TranslationError("Translation error")

            result = main(["input.srt", "output.srt"])

        self.assertEqual(result, 1)

    def test_main_keyboard_interrupt(self):
        """Test main function handling KeyboardInterrupt."""
        with patch("src.subtranslate.cli.handle_translate_command") as mock_handle:
            mock_handle.side_effect = KeyboardInterrupt()

            result = main(["input.srt", "output.srt"])

        self.assertEqual(result, 130)

    def test_main_unexpected_error(self):
        """Test main function handling unexpected error."""
        with patch("src.subtranslate.cli.handle_translate_command") as mock_handle:
            mock_handle.side_effect = Exception("Unexpected error")

            result = main(["input.srt", "output.srt"])

        self.assertEqual(result, 1)

    def test_main_no_args(self):
        """Test main function with no arguments."""
        result = main(None)

        # Should default to showing help and return appropriately
        # This might vary based on argparse implementation
        self.assertIsInstance(result, int)

    def test_main_verbose_error_handling(self):
        """Test main function with verbose error handling."""
        with patch("src.subtranslate.cli.parse_args") as mock_parse:
            mock_args = Mock()
            mock_args.command = "translate"
            mock_args.verbose = True
            mock_parse.return_value = mock_args

            with patch("src.subtranslate.cli.handle_translate_command") as mock_handle, patch(
                "traceback.print_exc"
            ) as mock_traceback:

                mock_handle.side_effect = SubtitleError("Test error")

                result = main(["--verbose", "input.srt", "output.srt"])

        self.assertEqual(result, 1)
        # Should print traceback in verbose mode
        mock_traceback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
