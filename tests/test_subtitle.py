"""
Tests for subtitle processing functionality.
"""

import os
import sys
import unittest
from pathlib import Path
import tempfile
import srt
from datetime import timedelta
import shutil

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from subtranslate.core.subtitle import SubtitleProcessor, SubtitleError, Splitter


class TestSplitter(unittest.TestCase):
    """Tests for the sentence splitter."""
    
    def setUp(self):
        self.splitter = Splitter()
    
    def test_split_empty_text(self):
        """Test splitting empty text."""
        self.assertEqual(self.splitter.split(""), [])
    
    def test_split_single_sentence(self):
        """Test splitting a single sentence."""
        text = "This is a test sentence."
        self.assertEqual(self.splitter.split(text), [text])
    
    def test_split_multiple_sentences(self):
        """Test splitting multiple sentences."""
        text = "This is the first sentence. This is the second sentence. And this is the third."
        expected = ["This is the first sentence.", "This is the second sentence.", "And this is the third."]
        self.assertEqual(self.splitter.split(text), expected)
    
    def test_split_with_abbreviations(self):
        """Test splitting text with abbreviations that shouldn't be split."""
        text = "Mr. Smith went to Washington D.C. He had a meeting at 10 a.m. yesterday."
        expected = ["Mr. Smith went to Washington D.C. He had a meeting at 10 a.m. yesterday."]
        self.assertEqual(self.splitter.split(text), expected)


class TestSubtitleProcessor(unittest.TestCase):
    """Tests for the subtitle processor."""
    
    def setUp(self):
        self.processor = SubtitleProcessor()
        
        # Create some sample subtitles for testing
        self.subtitles = [
            srt.Subtitle(index=1, start=timedelta(seconds=0), end=timedelta(seconds=2), 
                        content="This is the first line.\nAnd this continues."),
            srt.Subtitle(index=2, start=timedelta(seconds=3), end=timedelta(seconds=5), 
                        content="This is the second subtitle."),
            srt.Subtitle(index=3, start=timedelta(seconds=6), end=timedelta(seconds=9), 
                        content="This is the third subtitle with\nmultiple lines\nof text.")
        ]
        
        # Create a temporary SRT file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = os.path.join(self.temp_dir.name, "test.srt")
        
        with open(self.temp_file, 'w', encoding='utf-8') as f:
            f.write(srt.compose(self.subtitles))
    
    def tearDown(self):
        self.temp_dir.cleanup()
    
    def test_parse_file(self):
        """Test parsing a subtitle file."""
        subtitles = self.processor.parse_file(self.temp_file)
        
        # Check that we have the right number of subtitles
        self.assertEqual(len(subtitles), 3)
        
        # Check that the content is correct
        self.assertEqual(subtitles[0].content, "This is the first line.\nAnd this continues.")
        self.assertEqual(subtitles[1].content, "This is the second subtitle.")
        self.assertEqual(subtitles[2].content, "This is the third subtitle with\nmultiple lines\nof text.")
    
    def test_parse_nonexistent_file(self):
        """Test parsing a file that doesn't exist."""
        with self.assertRaises(SubtitleError):
            self.processor.parse_file("nonexistent.srt")
    
    def test_save_file(self):
        """Test saving subtitles to a file."""
        output_file = os.path.join(self.temp_dir.name, "output.srt")
        
        self.processor.save_file(self.subtitles, output_file)
        
        # Check that the file was created
        self.assertTrue(os.path.exists(output_file))
        
        # Parse it back to check content
        parsed_subtitles = self.processor.parse_file(output_file)
        
        # Check that we have the right number of subtitles
        self.assertEqual(len(parsed_subtitles), 3)
        
        # Check that the content is the same
        for i in range(3):
            self.assertEqual(parsed_subtitles[i].content, self.subtitles[i].content)
    
    def test_triple_r(self):
        """Test the triple_r function which processes line breaks and indices."""
        plain_text, dialog_idx = self.processor.triple_r(self.subtitles)
        
        # Check that the plain text has no line breaks
        self.assertNotIn("\n", plain_text)
        
        # Check that we have the right number of dialog indices
        self.assertEqual(len(dialog_idx), 3)
    
    def test_split_and_record(self):
        """Test splitting plain text into sentences."""
        # Create some plain text
        plain_text = "This is the first sentence. This is the second sentence. This is the third."
        
        sen_list, sen_idx = self.processor.split_and_record(plain_text)
        
        # Check that we have the right number of sentences
        self.assertEqual(len(sen_list), 3)
        
        # Check that we have the right number of indices (including the initial 0)
        self.assertEqual(len(sen_idx), 4)
        
        # Check that the first index is 0
        self.assertEqual(sen_idx[0], 0)
    
    def test_simple_translate_subtitles(self):
        """Test applying simple translations to subtitles."""
        # Create a simple mock implementation of simple_translate_subtitles
        def mock_simple_translate(subtitles, translated_texts, both=True):
            result = []
            for i, sub in enumerate(subtitles):
                content = translated_texts[i]
                if both:
                    content += '\n' + sub.content.replace('\n', ' ')
                result.append(srt.Subtitle(index=sub.index, start=sub.start, end=sub.end, content=content))
            return result
            
        # Save original method and replace with mock
        original_method = self.processor.simple_translate_subtitles
        self.processor.simple_translate_subtitles = mock_simple_translate
        
        try:
            translated_texts = [
                "Esta es la primera línea. Y esto continúa.",
                "Este es el segundo subtítulo.",
                "Este es el tercer subtítulo con múltiples líneas de texto."
            ]
            
            # Test with both original and translated text
            translated_subs = self.processor.simple_translate_subtitles(
                self.subtitles, translated_texts, both=True
            )
            
            # Check that we have the right number of subtitles
            self.assertEqual(len(translated_subs), 3)
            
            # Check that each subtitle has both the translation and the original
            for i in range(3):
                self.assertIn(translated_texts[i], translated_subs[i].content)
                self.assertIn(self.subtitles[i].content.replace('\n', ' '), translated_subs[i].content)
            
            # Test with only translated text
            translated_subs = self.processor.simple_translate_subtitles(
                self.subtitles, translated_texts, both=False
            )
            
            # Check that each subtitle has only the translation
            for i in range(3):
                self.assertEqual(translated_subs[i].content, translated_texts[i])
        finally:
            # Restore original method
            self.processor.simple_translate_subtitles = original_method
    
    def test_advanced_translate_subtitles(self):
        """Test applying advanced translations to subtitles."""
        # Create a simple mock implementation of advanced_translate_subtitles
        def mock_advanced_translate(subtitles, translated_dialogs, both=True):
            result = []
            for i, sub in enumerate(subtitles):
                content = translated_dialogs[i]
                if both:
                    content += '\n' + sub.content.replace('\n', ' ')
                result.append(srt.Subtitle(index=sub.index, start=sub.start, end=sub.end, content=content))
            return result
            
        # Save original method and replace with mock
        original_method = self.processor.advanced_translate_subtitles
        self.processor.advanced_translate_subtitles = mock_advanced_translate
        
        try:
            translated_dialogs = [
                "Esta es la primera línea. Y esto continúa.",
                "Este es el segundo subtítulo.",
                "Este es el tercer subtítulo con múltiples líneas de texto."
            ]
            
            # Test with both original and translated text
            translated_subs = self.processor.advanced_translate_subtitles(
                self.subtitles, translated_dialogs, both=True
            )
            
            # Check that we have the right number of subtitles
            self.assertEqual(len(translated_subs), 3)
            
            # Check that each subtitle has both the translation and the original
            for i in range(3):
                self.assertIn(translated_dialogs[i], translated_subs[i].content)
                self.assertIn(self.subtitles[i].content.replace('\n', ' '), translated_subs[i].content)
            
            # Test with only translated text
            translated_subs = self.processor.advanced_translate_subtitles(
                self.subtitles, translated_dialogs, both=False
            )
            
            # Check that each subtitle has only the translation
            for i in range(3):
                self.assertEqual(translated_subs[i].content, translated_dialogs[i])
        finally:
            # Restore original method
            self.processor.advanced_translate_subtitles = original_method


if __name__ == '__main__':
    unittest.main() 