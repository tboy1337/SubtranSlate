#!/usr/bin/env python3
"""
Simple test script to verify the translation service is working.
"""

import sys
import os

# Ensure the root directory is in the Python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from utilities.util_trans import Translator

def main():
    t = Translator()
    # Enable debug mode for more detailed output
    t.set_debug(True)
    
    print("Testing the translation service...")
    test_text = "Hello, this is a test of the translation service."
    
    # Test translation to Chinese
    print("\nTranslating to Chinese:")
    try:
        result = t.translate(test_text, 'en', 'zh-CN')
        print(f"Original: {test_text}")
        print(f"Translated: {result}")
        print("Translation to Chinese successful!")
    except Exception as e:
        print(f"Error translating to Chinese: {str(e)}")
    
    # Test translation to German
    print("\nTranslating to German:")
    try:
        result = t.translate(test_text, 'en', 'de')
        print(f"Original: {test_text}")
        print(f"Translated: {result}")
        print("Translation to German successful!")
    except Exception as e:
        print(f"Error translating to German: {str(e)}")

if __name__ == '__main__':
    main() 