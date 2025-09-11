"""
Comprehensive tests for subtitle processing functionality - covering gaps.
"""

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

from src.subtranslate.core.subtitle import Splitter, SubtitleError, SubtitleProcessor


class TestSubtitleProcessorComprehensive(unittest.TestCase):
    """Comprehensive tests for the subtitle processor to fill coverage gaps."""

    def setUp(self):
        self.processor = SubtitleProcessor()

        # Create more comprehensive test subtitles
        self.subtitles = [
            srt.Subtitle(
                index=1, start=timedelta(seconds=0), end=timedelta(seconds=2), content="Hello world"
            ),
            srt.Subtitle(
                index=2,
                start=timedelta(seconds=3),
                end=timedelta(seconds=5),
                content="This is a test.\nWith multiple lines.",
            ),
            srt.Subtitle(
                index=3,
                start=timedelta(seconds=6),
                end=timedelta(seconds=9),
                content="Final subtitle",
            ),
        ]

        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_file_unicode_decode_error(self):
        """Test parse_file with unicode decode error."""
        # Create a file with binary data that can't be decoded as UTF-8
        test_file = os.path.join(self.temp_dir.name, "binary.srt")
        with open(test_file, "wb") as f:
            f.write(b"\xff\xfe\x00\x00")  # Invalid UTF-8 sequence

        with self.assertRaises(SubtitleError) as cm:
            self.processor.parse_file(test_file, encoding="UTF-8")

        self.assertIn("Failed to decode subtitle file", str(cm.exception))

    def test_parse_file_srt_parse_error(self):
        """Test parse_file with SRT parsing error."""
        # Create a malformed SRT file
        test_file = os.path.join(self.temp_dir.name, "malformed.srt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("This is not a valid SRT file\nNo timecodes or proper format")

        with self.assertRaises(SubtitleError) as cm:
            self.processor.parse_file(test_file, encoding="UTF-8")

        self.assertIn("Failed to parse SRT file", str(cm.exception))

    def test_parse_file_general_error(self):
        """Test parse_file with general IO error."""
        with patch("builtins.open", side_effect=IOError("IO Error")):
            with self.assertRaises(SubtitleError) as cm:
                self.processor.parse_file("test.srt")

        self.assertIn("Error reading subtitle file", str(cm.exception))

    def test_save_file_with_invalid_subtitle_objects(self):
        """Test save_file with objects that aren't proper srt.Subtitle objects."""
        # Create mock objects that aren't srt.Subtitle instances
        mock_subtitle = Mock()
        mock_subtitle.index = 1
        mock_subtitle.start = timedelta(seconds=0)
        mock_subtitle.end = timedelta(seconds=2)
        mock_subtitle.content = "Test content"

        test_file = os.path.join(self.temp_dir.name, "output.srt")

        # Should handle conversion gracefully
        self.processor.save_file([mock_subtitle], test_file)

        # File should exist and be readable
        self.assertTrue(os.path.exists(test_file))

    def test_save_file_conversion_error(self):
        """Test save_file when subtitle conversion fails."""
        # Create a mock that raises an exception during conversion
        mock_subtitle = Mock()
        mock_subtitle.__class__ = object  # Not an srt.Subtitle

        # Make attribute access raise exceptions
        def side_effect(attr):
            raise Exception("Attribute error")

        mock_subtitle.__getattr__ = side_effect

        test_file = os.path.join(self.temp_dir.name, "output.srt")

        # Should handle conversion errors gracefully and still save
        with patch("src.subtranslate.core.subtitle.logger.warning"):
            self.processor.save_file([mock_subtitle], test_file)

        self.assertTrue(os.path.exists(test_file))

    def test_save_file_write_error(self):
        """Test save_file with write error."""
        test_file = "/invalid/path/output.srt"  # Invalid path

        with self.assertRaises(SubtitleError) as cm:
            self.processor.save_file(self.subtitles, test_file)

        self.assertIn("Failed to save subtitles", str(cm.exception))

    def test_compute_mass_list_edge_cases(self):
        """Test compute_mass_list with edge cases."""
        # Test with empty lists
        result = self.processor.compute_mass_list([], [0])
        self.assertEqual(result, [])

        # Test with single dialog
        result = self.processor.compute_mass_list([10], [0, 15])
        self.assertEqual(result, [[(1, 10)]])

        # Test complex scenario
        dialog_idx = [5, 10, 20, 25]
        sen_idx = [0, 12, 30]
        result = self.processor.compute_mass_list(dialog_idx, sen_idx)

        # Should properly map dialogues to sentences
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_get_nearest_space_edge_cases(self):
        """Test get_nearest_space with edge cases."""
        # Empty sentence
        result = self.processor.get_nearest_space("", 0)
        self.assertEqual(result, 0)

        # No spaces
        result = self.processor.get_nearest_space("nospace", 3)
        self.assertEqual(result, 3)

        # Only left space available
        result = self.processor.get_nearest_space("hello world", 11)
        self.assertEqual(result, 6)  # After "hello "

        # Only right space available
        result = self.processor.get_nearest_space("hello world", 0)
        self.assertEqual(result, 6)  # After "hello "

        # Both sides available, choose nearest
        sentence = "one two three four five"
        result = self.processor.get_nearest_space(sentence, 10)
        # Should choose the nearest space
        self.assertIsInstance(result, int)

    @patch("src.subtranslate.core.subtitle.JIEBA_AVAILABLE", False)
    def test_get_nearest_split_cn_no_jieba(self):
        """Test get_nearest_split_cn when jieba is not available."""
        result = self.processor.get_nearest_split_cn("中文测试", 2, 0)
        self.assertEqual(result, 2)  # Should return current_idx when jieba unavailable

    @patch("src.subtranslate.core.subtitle.JIEBA_AVAILABLE", True)
    @patch("jieba.cut")
    def test_get_nearest_split_cn_with_jieba(self, mock_jieba_cut):
        """Test get_nearest_split_cn with jieba available."""
        mock_jieba_cut.return_value = ["中", "文", "测", "试"]

        result = self.processor.get_nearest_split_cn("中文测试", 2, 0)

        self.assertIsInstance(result, int)
        mock_jieba_cut.assert_called_once()

    @patch("src.subtranslate.core.subtitle.JIEBA_AVAILABLE", True)
    @patch("jieba.cut")
    def test_get_nearest_split_cn_with_comma(self, mock_jieba_cut):
        """Test get_nearest_split_cn with Chinese comma."""
        mock_jieba_cut.return_value = ["中", "文", "，", "测", "试"]

        result = self.processor.get_nearest_split_cn("中文，测试", 2, 0)

        self.assertIsInstance(result, int)

    @patch("src.subtranslate.core.subtitle.JIEBA_AVAILABLE", True)
    @patch("jieba.cut")
    def test_get_nearest_split_cn_error(self, mock_jieba_cut):
        """Test get_nearest_split_cn with jieba error."""
        mock_jieba_cut.side_effect = Exception("Jieba error")

        result = self.processor.get_nearest_split_cn("中文测试", 2, 0)

        # Should return current_idx on error
        self.assertEqual(result, 2)

    def test_sen_list2dialog_list_empty_inputs(self):
        """Test sen_list2dialog_list with empty inputs."""
        # Empty sentence list
        result = self.processor.sen_list2dialog_list([], [[]])
        self.assertEqual(result, [])

        # Empty mass list
        result = self.processor.sen_list2dialog_list(["test"], [])
        self.assertEqual(result, [])

    def test_sen_list2dialog_list_no_dialogues(self):
        """Test sen_list2dialog_list when mass_list indicates no dialogues."""
        # Mass list with no dialogues
        mass_list = []
        result = self.processor.sen_list2dialog_list(["test"], mass_list)
        self.assertEqual(result, [])

    def test_sen_list2dialog_list_index_out_of_range(self):
        """Test sen_list2dialog_list with index out of range."""
        sen_list = ["sentence1", "sentence2"]
        mass_list = [[(1, 10)]]  # Only one sentence mapping, but we have two sentences

        with patch("src.subtranslate.core.subtitle.logger.warning"):
            result = self.processor.sen_list2dialog_list(sen_list, mass_list)

        # Should handle gracefully
        self.assertIsInstance(result, list)

    def test_sen_list2dialog_list_empty_record(self):
        """Test sen_list2dialog_list with empty record."""
        sen_list = ["sentence1"]
        mass_list = [[]]  # Empty record

        with patch("src.subtranslate.core.subtitle.logger.warning"):
            result = self.processor.sen_list2dialog_list(sen_list, mass_list)

        # Should handle gracefully
        self.assertIsInstance(result, list)

    def test_sen_list2dialog_list_complex_scenario(self):
        """Test sen_list2dialog_list with complex multi-dialog sentence."""
        sen_list = ["This is a long sentence that spans multiple subtitles"]
        mass_list = [[(1, 15), (2, 30), (3, 52)]]  # One sentence spans three dialogues

        result = self.processor.sen_list2dialog_list(sen_list, mass_list, space=True, cn=False)

        self.assertEqual(len(result), 3)  # Should create 3 dialogues

        # All parts combined should equal original sentence
        combined = "".join(result)
        self.assertEqual(combined, sen_list[0])

    def test_sen_list2dialog_list_chinese_mode(self):
        """Test sen_list2dialog_list with Chinese mode."""
        sen_list = ["这是一个测试句子"]
        mass_list = [[(1, 4), (2, 9)]]  # One sentence spans two dialogues

        with patch.object(self.processor, "get_nearest_split_cn", return_value=4) as mock_split:
            result = self.processor.sen_list2dialog_list(sen_list, mass_list, space=False, cn=True)

        self.assertEqual(len(result), 2)
        mock_split.assert_called()

    def test_sen_list2dialog_list_dialog_index_out_of_bounds(self):
        """Test sen_list2dialog_list when dialog index is out of bounds."""
        sen_list = ["test"]
        # Mass list with dialog index larger than will be created
        mass_list = [[(10, 4)]]  # Dialog 10 but we'll only have space for fewer

        with patch("src.subtranslate.core.subtitle.logger.warning"):
            result = self.processor.sen_list2dialog_list(sen_list, mass_list)

        # Should handle gracefully without crashing
        self.assertIsInstance(result, list)

    def test_simple_translate_subtitles_count_mismatch(self):
        """Test simple_translate_subtitles with mismatched counts."""
        translated_texts = ["Only one translation"]  # But we have 3 subtitles

        with self.assertRaises(SubtitleError) as cm:
            self.processor.simple_translate_subtitles(self.subtitles, translated_texts, both=True)

        self.assertIn("Subtitle count mismatch", str(cm.exception))

    def test_advanced_translate_subtitles_count_mismatch(self):
        """Test advanced_translate_subtitles with mismatched counts."""
        translated_dialogs = ["Only one translation"]  # But we have 3 subtitles

        with self.assertRaises(SubtitleError) as cm:
            self.processor.advanced_translate_subtitles(
                self.subtitles, translated_dialogs, both=True
            )

        self.assertIn("Subtitle count mismatch", str(cm.exception))

    def test_to_serialized(self):
        """Test to_serialized method."""
        result = self.processor.to_serialized(self.subtitles)

        self.assertEqual(len(result), 3)
        self.assertIsInstance(result, list)

        for item in result:
            self.assertIn("index", item)
            self.assertIn("start_time", item)
            self.assertIn("end_time", item)
            self.assertIn("content", item)

    def test_to_serialized_with_translated_content(self):
        """Test to_serialized with subtitles that have translated content."""
        # Add translated content to subtitles
        for sub in self.subtitles:
            sub.translated_content = f"Translated: {sub.content}"

        result = self.processor.to_serialized(self.subtitles)

        for item in result:
            self.assertIn("translated_content", item)
            self.assertIsNotNone(item["translated_content"])

    def test_from_serialized(self):
        """Test from_serialized method."""
        serialized_data = [
            {
                "index": 1,
                "start_time": timedelta(seconds=0),
                "end_time": timedelta(seconds=2),
                "content": "Test content",
            },
            {
                "index": 2,
                "start_time": timedelta(seconds=3),
                "end_time": timedelta(seconds=5),
                "content": "Another test",
                "translated_content": "Otra prueba",
            },
        ]

        result = self.processor.from_serialized(serialized_data)

        self.assertEqual(len(result), 2)

        # Check first subtitle
        self.assertEqual(result[0].index, 1)
        self.assertEqual(result[0].content, "Test content")

        # Check second subtitle with translated content
        self.assertEqual(result[1].index, 2)
        self.assertEqual(result[1].content, "Another test")
        self.assertEqual(result[1].translated_content, "Otra prueba")

    def test_simple_translate_subtitles_both_false(self):
        """Test simple_translate_subtitles with both=False."""
        translated_texts = ["Hola mundo", "Esta es una prueba", "Subtítulo final"]

        result = self.processor.simple_translate_subtitles(
            self.subtitles, translated_texts, both=False
        )

        self.assertEqual(len(result), 3)

        # Should only contain translations, not original text
        for i, sub in enumerate(result):
            self.assertEqual(sub.content, translated_texts[i])
            self.assertNotIn("Hello", sub.content)  # Original shouldn't be there

    def test_advanced_translate_subtitles_both_false(self):
        """Test advanced_translate_subtitles with both=False."""
        translated_dialogs = ["Hola mundo", "Esta es una prueba", "Subtítulo final"]

        result = self.processor.advanced_translate_subtitles(
            self.subtitles, translated_dialogs, both=False
        )

        self.assertEqual(len(result), 3)

        # Should only contain translations, not original text
        for i, sub in enumerate(result):
            self.assertEqual(sub.content, translated_dialogs[i])
            self.assertNotIn("Hello", sub.content)  # Original shouldn't be there


class TestSplitterComprehensive(unittest.TestCase):
    """Comprehensive tests for Splitter to fill coverage gaps."""

    def setUp(self):
        self.splitter = Splitter()

    def test_split_with_question_marks(self):
        """Test splitting with question marks."""
        text = "What is this? Is it a test? Yes, it is."
        result = self.splitter.split(text)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "What is this?")
        self.assertEqual(result[1], "Is it a test?")
        self.assertEqual(result[2], "Yes, it is.")

    def test_split_with_exclamation_marks(self):
        """Test splitting with exclamation marks."""
        text = "Hello! How are you! I'm fine!"
        result = self.splitter.split(text)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "Hello!")
        self.assertEqual(result[1], "How are you!")
        self.assertEqual(result[2], "I'm fine!")

    def test_split_mixed_punctuation(self):
        """Test splitting with mixed punctuation."""
        text = "Is this working? Yes! It seems to be. Good."
        result = self.splitter.split(text)

        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], "Is this working?")
        self.assertEqual(result[1], "Yes!")
        self.assertEqual(result[2], "It seems to be.")
        self.assertEqual(result[3], "Good.")

    def test_split_no_sentence_endings(self):
        """Test splitting text with no sentence endings."""
        text = "This has no sentence endings"
        result = self.splitter.split(text)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], text)

    def test_split_only_whitespace(self):
        """Test splitting whitespace-only text."""
        text = "   \t\n  "
        result = self.splitter.split(text)

        # Should return filtered results with no empty strings
        if result:  # If any non-empty results
            for item in result:
                self.assertTrue(item.strip())

    def test_split_complex_abbreviations(self):
        """Test splitting with complex abbreviations."""
        text = (
            "Dr. John Smith Jr. visited the U.S.A. last month. He met Prof. Jane Doe Ph.D. there."
        )
        result = self.splitter.split(text)

        # Should not split on abbreviations
        self.assertEqual(len(result), 2)
        self.assertIn("Dr. John Smith Jr.", result[0])
        self.assertIn("U.S.A.", result[0])
        self.assertIn("Prof. Jane Doe Ph.D.", result[1])


if __name__ == "__main__":
    unittest.main()
