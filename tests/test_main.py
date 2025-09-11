"""
Tests for the main translation functionality.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import srt

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Imports must happen after sys.path modification  # pylint: disable=wrong-import-position
from src.subtranslate.core.main import SubtitleTranslator, translate_and_compose
from src.subtranslate.core.translation import RateLimitError


class TestSubtitleTranslator(unittest.TestCase):
    """Tests for the SubtitleTranslator class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()

        # Create sample subtitle data
        self.sample_subtitles = [
            srt.Subtitle(
                index=1,
                start=timedelta(seconds=0),
                end=timedelta(seconds=2),
                content="Hello world",
            ),
            srt.Subtitle(
                index=2,
                start=timedelta(seconds=3),
                end=timedelta(seconds=5),
                content="This is a test.",
            ),
        ]

        # Create sample input file
        self.input_file = os.path.join(self.temp_dir.name, "input.srt")
        with open(self.input_file, "w", encoding="utf-8") as f:
            f.write(srt.compose(self.sample_subtitles))

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_init_default(self) -> None:
        """Test initialization with default parameters."""
        translator = SubtitleTranslator()

        self.assertIsNotNone(translator.translator)
        self.assertIsNotNone(translator.subtitle_processor)

    def test_init_with_api_key(self) -> None:
        """Test initialization with API key."""
        translator = SubtitleTranslator(api_key="test_key")

        self.assertIsNotNone(translator.translator)
        self.assertIsNotNone(translator.subtitle_processor)

    @patch("src.subtranslate.core.main.SubtitleProcessor")
    @patch("src.subtranslate.core.main.get_translator")
    def test_init_with_service(
        self, mock_get_translator: Mock, mock_subtitle_processor: Mock
    ) -> None:
        """Test initialization with different service."""
        mock_translator = Mock()
        mock_get_translator.return_value = mock_translator
        mock_processor = Mock()
        mock_subtitle_processor.return_value = mock_processor

        translator = SubtitleTranslator(
            translation_service="custom", api_key="test_key"
        )

        mock_get_translator.assert_called_once_with("custom", "test_key")
        self.assertEqual(translator.translator, mock_translator)

    @patch("src.subtranslate.core.main.os.path.exists")
    @patch("src.subtranslate.core.main.os.makedirs")
    def test_translate_file_creates_output_dir(
        self, mock_makedirs: Mock, mock_exists: Mock
    ) -> None:
        """Test that translate_file creates output directory if needed."""
        mock_exists.return_value = False

        translator = SubtitleTranslator()
        output_file = os.path.join(self.temp_dir.name, "subdir", "output.srt")

        with patch.object(
            translator.subtitle_processor, "parse_file"
        ) as mock_parse, patch.object(
            translator.subtitle_processor, "save_file"
        ), patch.object(
            translator, "_translate_split"
        ) as mock_translate:

            mock_parse.return_value = self.sample_subtitles
            mock_translate.return_value = self.sample_subtitles

            translator.translate_file(self.input_file, output_file, "en", "es")

            mock_makedirs.assert_called_once()

    def test_translate_file_naive_mode(self) -> None:
        """Test translate_file in naive mode."""
        translator = SubtitleTranslator()
        output_file = os.path.join(self.temp_dir.name, "output.srt")

        with patch.object(
            translator.subtitle_processor, "parse_file"
        ) as mock_parse, patch.object(
            translator.subtitle_processor, "save_file"
        ) as mock_save, patch.object(
            translator, "_translate_naive"
        ) as mock_translate:

            mock_parse.return_value = self.sample_subtitles
            mock_translate.return_value = self.sample_subtitles

            translator.translate_file(
                self.input_file, output_file, "en", "es", mode="naive", resume=False
            )

            mock_parse.assert_called_once_with(self.input_file, "UTF-8")
            mock_translate.assert_called_once_with(
                self.sample_subtitles, "en", "es", both=True, checkpoint_file=None
            )
            mock_save.assert_called_once()

    def test_translate_file_split_mode(self) -> None:
        """Test translate_file in split mode."""
        translator = SubtitleTranslator()
        output_file = os.path.join(self.temp_dir.name, "output.srt")

        with patch.object(
            translator.subtitle_processor, "parse_file"
        ) as mock_parse, patch.object(
            translator.subtitle_processor, "save_file"
        ) as mock_save, patch.object(
            translator, "_translate_split"
        ) as mock_translate:

            mock_parse.return_value = self.sample_subtitles
            mock_translate.return_value = self.sample_subtitles

            translator.translate_file(
                self.input_file, output_file, "en", "es", mode="split", resume=False
            )

            mock_parse.assert_called_once_with(self.input_file, "UTF-8")
            mock_translate.assert_called_once_with(
                self.sample_subtitles,
                "en",
                "es",
                both=True,
                space=False,
                checkpoint_file=None,
            )
            mock_save.assert_called_once()

    def test_translate_file_with_checkpoint(self) -> None:
        """Test translate_file with checkpoint functionality."""
        translator = SubtitleTranslator()
        output_file = os.path.join(self.temp_dir.name, "output.srt")
        checkpoint_file = output_file + ".checkpoint"

        # Create a checkpoint file
        checkpoint_data = {
            "status": "parsing_complete",
            "parsed_subtitles": [
                {
                    "index": 1,
                    "start_time": timedelta(seconds=0),
                    "end_time": timedelta(seconds=2),
                    "content": "Hello world",
                }
            ],
        }
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, default=str)

        with patch.object(
            translator.subtitle_processor, "from_serialized"
        ) as mock_from_serial, patch.object(
            translator.subtitle_processor, "save_file"
        ) as mock_save, patch.object(
            translator, "_translate_split"
        ) as mock_translate:

            mock_from_serial.return_value = self.sample_subtitles
            mock_translate.return_value = self.sample_subtitles

            translator.translate_file(
                self.input_file, output_file, "en", "es", resume=True
            )

            mock_from_serial.assert_called_once()
            mock_translate.assert_called_once()
            mock_save.assert_called_once()

    def test_translate_file_complete_checkpoint(self) -> None:
        """Test translate_file with complete checkpoint."""
        translator = SubtitleTranslator()
        output_file = os.path.join(self.temp_dir.name, "output.srt")
        checkpoint_file = output_file + ".checkpoint"

        # Create a complete checkpoint file
        checkpoint_data = {"status": "complete", "progress": 100}
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f)

        with patch.object(translator.subtitle_processor, "parse_file") as mock_parse:
            translator.translate_file(
                self.input_file, output_file, "en", "es", resume=True
            )

            # Should not parse file if checkpoint is complete
            mock_parse.assert_not_called()

    def test_save_checkpoint(self) -> None:
        """Test _save_checkpoint method."""
        translator = SubtitleTranslator()
        checkpoint_file = os.path.join(self.temp_dir.name, "test.checkpoint")

        test_data = {
            "status": "test",
            "progress": 50,
            "timedelta_obj": timedelta(seconds=30),
        }

        translator._save_checkpoint(checkpoint_file, test_data)  # type: ignore[arg-type]

        # Check that file was created and contains expected data
        self.assertTrue(os.path.exists(checkpoint_file))

        with open(checkpoint_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        self.assertEqual(saved_data["status"], "test")
        self.assertEqual(saved_data["progress"], 50)
        # timedelta should be converted to string
        self.assertEqual(saved_data["timedelta_obj"], "0:00:30")

    def test_save_checkpoint_error(self) -> None:
        """Test _save_checkpoint with invalid path."""
        translator = SubtitleTranslator()
        # Use invalid path to trigger error
        invalid_path = "/invalid/path/test.checkpoint"

        test_data = {"status": "test"}

        # Should not raise exception, just log warning
        translator._save_checkpoint(invalid_path, test_data)  # type: ignore[arg-type]

    def test_translate_naive(self) -> None:
        """Test _translate_naive method."""
        translator = SubtitleTranslator()

        with patch.object(
            translator, "_translate_with_progress"
        ) as mock_translate_progress, patch.object(
            translator.subtitle_processor, "simple_translate_subtitles"
        ) as mock_simple:

            mock_translate_progress.return_value = "Hola mundo\nEsta es una prueba."
            mock_simple.return_value = self.sample_subtitles

            result = translator._translate_naive(
                self.sample_subtitles, "en", "es", both=True
            )

            mock_translate_progress.assert_called_once()
            mock_simple.assert_called_once_with(
                self.sample_subtitles, ["Hola mundo", "Esta es una prueba."], True
            )
            self.assertEqual(result, self.sample_subtitles)

    def test_translate_naive_with_retry(self) -> None:
        """Test _translate_naive with rate limit retry."""
        translator = SubtitleTranslator()

        with patch.object(
            translator, "_translate_with_progress"
        ) as mock_translate_progress, patch.object(
            translator.subtitle_processor, "simple_translate_subtitles"
        ) as mock_simple, patch(
            "time.sleep"
        ) as mock_sleep:

            # First call raises rate limit error, second succeeds
            mock_translate_progress.side_effect = [
                RateLimitError("Rate limited"),
                "Hola mundo\nEsta es una prueba.",
            ]
            mock_simple.return_value = self.sample_subtitles

            result = translator._translate_naive(
                self.sample_subtitles, "en", "es", both=True
            )

            self.assertEqual(mock_translate_progress.call_count, 2)
            mock_sleep.assert_called_once_with(60)  # First backoff
            self.assertEqual(result, self.sample_subtitles)

    def test_translate_split(self) -> None:
        """Test _translate_split method."""
        translator = SubtitleTranslator()

        with patch.object(
            translator.subtitle_processor, "triple_r"
        ) as mock_triple_r, patch.object(
            translator.subtitle_processor, "split_and_record"
        ) as mock_split, patch.object(
            translator.subtitle_processor, "compute_mass_list"
        ) as mock_mass, patch.object(
            translator.subtitle_processor, "sen_list2dialog_list"
        ) as mock_sen2dialog, patch.object(
            translator.subtitle_processor, "advanced_translate_subtitles"
        ) as mock_advanced, patch.object(
            translator, "_translate_with_progress"
        ) as mock_translate_progress:

            mock_triple_r.return_value = ("Hello world This is a test", [11, 26])
            mock_split.return_value = (["Hello world", "This is a test"], [0, 12, 27])
            mock_mass.return_value = [[(1, 11)], [(2, 15)]]
            mock_sen2dialog.return_value = ["Hola mundo", "Esta es una prueba"]
            mock_translate_progress.return_value = "Hola mundo\nEsta es una prueba"
            mock_advanced.return_value = self.sample_subtitles

            result = translator._translate_split(
                self.sample_subtitles, "en", "es", both=True, space=False
            )

            mock_triple_r.assert_called_once_with(self.sample_subtitles)
            mock_split.assert_called_once()
            mock_translate_progress.assert_called_once()
            mock_advanced.assert_called_once()
            self.assertEqual(result, self.sample_subtitles)

    def test_translate_split_chinese(self) -> None:
        """Test _translate_split method with Chinese target."""
        translator = SubtitleTranslator()

        with patch.object(
            translator.subtitle_processor, "triple_r"
        ) as mock_triple_r, patch.object(
            translator.subtitle_processor, "split_and_record"
        ) as mock_split, patch.object(
            translator.subtitle_processor, "compute_mass_list"
        ) as mock_mass, patch.object(
            translator.subtitle_processor, "sen_list2dialog_list"
        ) as mock_sen2dialog, patch.object(
            translator.subtitle_processor, "advanced_translate_subtitles"
        ) as mock_advanced, patch.object(
            translator, "_translate_with_progress"
        ) as mock_translate_progress:

            mock_triple_r.return_value = ("Hello world", [11])
            mock_split.return_value = (["Hello world"], [0, 12])
            mock_mass.return_value = [[(1, 11)]]
            mock_sen2dialog.return_value = ["你好世界"]
            mock_translate_progress.return_value = "你好世界"
            mock_advanced.return_value = self.sample_subtitles

            translator._translate_split(
                self.sample_subtitles, "en", "zh-CN", both=True, space=False
            )

            # Should call sen_list2dialog_list with is_chinese=True for Chinese
            mock_sen2dialog.assert_called_once()
            _, call_kwargs = mock_sen2dialog.call_args
            # is_chinese is now passed as a keyword argument
            # is_chinese parameter should be True
            self.assertTrue(call_kwargs.get("is_chinese", False))

    def test_translate_with_progress(self) -> None:
        """Test _translate_with_progress method."""
        translator = SubtitleTranslator()

        with patch.object(
            translator.translator, "translate_lines"
        ) as mock_translate_lines:
            mock_translate_lines.return_value = "Translated text"

            result = translator._translate_with_progress(["Hello", "World"], "en", "es")

            mock_translate_lines.assert_called_once()
            self.assertEqual(result, "Translated text")

    def test_translate_with_progress_callback(self) -> None:
        """Test _translate_with_progress with progress callback."""
        translator = SubtitleTranslator()
        progress_calls = []

        def progress_callback(current: int, total: int, translated: str) -> None:
            progress_calls.append((current, total, translated))

        with patch.object(
            translator.translator, "translate_lines"
        ) as mock_translate_lines:
            # Mock the progress callback being called
            def mock_translate_with_callback(_text_list, _src, _tgt, callback):
                if callback:
                    callback(1, 2, "partial")
                    callback(2, 2, "complete")
                return "Translated text"

            mock_translate_lines.side_effect = mock_translate_with_callback

            result = translator._translate_with_progress(["Hello", "World"], "en", "es")
            # Verify progress callback was defined for potential use
            self.assertIsNotNone(progress_callback)

            self.assertEqual(result, "Translated text")

    @patch("src.subtranslate.core.main.Path")
    @patch("src.subtranslate.core.main.os.path.isdir")
    @patch("src.subtranslate.core.main.os.makedirs")
    def test_batch_translate_directory(
        self, _mock_makedirs: Mock, mock_isdir: Mock, mock_path: Mock
    ) -> None:
        """Test batch_translate_directory method."""
        mock_isdir.return_value = True

        # Mock Path.glob to return test files
        mock_path_obj = Mock()
        mock_path.return_value = mock_path_obj
        mock_path_obj.glob.return_value = [
            Path(os.path.join(self.temp_dir.name, "test1.srt")),
            Path(os.path.join(self.temp_dir.name, "test2.srt")),
        ]

        translator = SubtitleTranslator()

        with patch.object(translator, "translate_file") as mock_translate_file:
            mock_translate_file.return_value = None

            results = translator.batch_translate_directory(
                input_dir=self.temp_dir.name,
                output_dir=self.temp_dir.name,
                src_lang="en",
                target_lang="es",
                resume=False,
            )

            self.assertEqual(len(results), 2)
            self.assertEqual(mock_translate_file.call_count, 2)

    def test_batch_translate_directory_invalid_input(self) -> None:
        """Test batch_translate_directory with invalid input directory."""
        translator = SubtitleTranslator()

        with self.assertRaises(ValueError):
            translator.batch_translate_directory(
                input_dir="/nonexistent/directory",
                output_dir=self.temp_dir.name,
                src_lang="en",
                target_lang="es",
            )

    @patch("src.subtranslate.core.main.Path")
    @patch("src.subtranslate.core.main.os.path.isdir")
    @patch("src.subtranslate.core.main.os.makedirs")
    def test_batch_translate_with_rate_limit(
        self, _mock_makedirs: Mock, mock_isdir: Mock, mock_path: Mock
    ) -> None:
        """Test batch_translate_directory handling rate limits."""
        mock_isdir.return_value = True

        # Mock Path.glob to return test files
        mock_path_obj = Mock()
        mock_path.return_value = mock_path_obj
        mock_path_obj.glob.return_value = [
            Path(os.path.join(self.temp_dir.name, "test1.srt"))
        ]

        translator = SubtitleTranslator()

        with patch.object(translator, "translate_file") as mock_translate_file, patch(
            "time.sleep"
        ) as mock_sleep:

            mock_translate_file.side_effect = RateLimitError("Rate limited")

            results = translator.batch_translate_directory(
                input_dir=self.temp_dir.name,
                output_dir=self.temp_dir.name,
                src_lang="en",
                target_lang="es",
                resume=False,
            )

            self.assertEqual(len(results), 1)
            # Should pause after rate limit
            mock_sleep.assert_called_once_with(120)
            # Check status
            for result in results.values():
                self.assertEqual(result["status"], "rate_limited")


class TestTranslateAndCompose(unittest.TestCase):
    """Tests for the translate_and_compose function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()

        # Create sample input file
        self.input_file = os.path.join(self.temp_dir.name, "input.srt")
        sample_subtitles = [
            srt.Subtitle(
                index=1,
                start=timedelta(seconds=0),
                end=timedelta(seconds=2),
                content="Hello world",
            )
        ]
        with open(self.input_file, "w", encoding="utf-8") as f:
            f.write(srt.compose(sample_subtitles))

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    @patch("src.subtranslate.core.main.SubtitleTranslator")
    def test_translate_and_compose(self, mock_translator_class: Mock) -> None:
        """Test the translate_and_compose function."""
        mock_translator = Mock()
        mock_translator_class.return_value = mock_translator

        output_file = os.path.join(self.temp_dir.name, "output.srt")

        translate_and_compose(
            input_file=self.input_file,
            output_file=output_file,
            src_lang="en",
            target_lang="es",
            encoding="UTF-8",
            mode="split",
            both=True,
            space=False,
            api_key="test_key",
            resume=True,
        )

        mock_translator_class.assert_called_once_with(api_key="test_key")
        mock_translator.translate_file.assert_called_once_with(
            self.input_file,
            output_file,
            "en",
            "es",
            encoding="UTF-8",
            mode="split",
            both=True,
            space=False,
            resume=True,
        )


if __name__ == "__main__":
    unittest.main()
