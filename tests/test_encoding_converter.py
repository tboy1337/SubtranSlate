#!/usr/bin/env python3
"""
Tests for the encoding converter utility.
"""

import os
import tempfile
import unittest
from pathlib import Path

from src.subtranslate.utilities.encoding_converter import (
    detect_encoding,
    convert_subtitle_encoding,
    convert_to_multiple_encodings,
    get_recommended_encodings
)

class TestEncodingConverter(unittest.TestCase):
    """Test the encoding converter functionality."""
    
    def setUp(self):
        """Create a temporary file with sample content for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = os.path.join(self.temp_dir.name, "sample.srt")
        
        # Create a sample subtitle file with UTF-8 encoding
        sample_content = """1
00:00:01,000 --> 00:00:05,000
This is a sample subtitle file.
Some characters: ไทย 中文 日本語 한국어

2
00:00:06,000 --> 00:00:10,000
More text with special characters:
áéíóú äëïöü ñ ç
"""
        with open(self.temp_file, 'w', encoding='utf-8') as f:
            f.write(sample_content)
    
    def tearDown(self):
        """Clean up temporary files."""
        self.temp_dir.cleanup()
    
    def test_detect_encoding(self):
        """Test that encoding detection works."""
        detected = detect_encoding(self.temp_file)
        self.assertIsNotNone(detected)
        # Should detect UTF-8 or UTF-8-sig
        self.assertTrue(detected.lower() in ['utf-8', 'utf-8-sig'])
    
    def test_convert_encoding(self):
        """Test converting a file to a different encoding."""
        output_file = os.path.join(self.temp_dir.name, "converted.srt")
        result = convert_subtitle_encoding(
            self.temp_file, output_file, "iso8859-1", "utf-8"
        )
        self.assertTrue(result)
        self.assertTrue(os.path.exists(output_file))
        
        # Read back and check if it's readable
        try:
            with open(output_file, 'r', encoding='iso8859-1') as f:
                content = f.read()
                # Non-Latin characters might be replaced with ? or other characters
                # but the file should be readable in the target encoding
                self.assertTrue(len(content) > 0)
        except Exception as e:
            self.fail(f"Failed to read converted file: {e}")
    
    def test_convert_multiple_encodings(self):
        """Test converting a file to multiple encodings."""
        result = convert_to_multiple_encodings(
            self.temp_file, 
            self.temp_dir.name, 
            ["utf-8-sig", "cp1252"]
        )
        
        # Check that the function reported success for at least UTF-8-sig
        self.assertTrue("utf-8-sig" in result)
        self.assertTrue(result["utf-8-sig"])
        
        # Check the files were created
        utf8_sig_file = os.path.join(self.temp_dir.name, "sample-utf-8-sig.srt")
        self.assertTrue(os.path.exists(utf8_sig_file))
    
    def test_get_recommended_encodings(self):
        """Test getting recommended encodings for different languages."""
        # Check Thai encodings
        thai_encodings = get_recommended_encodings("th")
        self.assertIn("tis-620", thai_encodings)
        self.assertIn("cp874", thai_encodings)
        
        # Check Chinese encodings
        chinese_encodings = get_recommended_encodings("zh-CN")
        self.assertIn("gb2312", chinese_encodings)
        
        # Check default encodings for unknown language
        default_encodings = get_recommended_encodings("xx")
        self.assertIn("utf-8", default_encodings)
        self.assertIn("cp1252", default_encodings)


if __name__ == "__main__":
    unittest.main() 