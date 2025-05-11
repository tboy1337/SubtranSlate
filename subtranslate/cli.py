#!/usr/bin/env python3
"""
Command-line interface for SubtranSlate.
"""

import argparse
import os
import sys
import logging
from typing import List, Optional, Dict
import traceback
from pathlib import Path

from subtranslate.core.main import SubtitleTranslator
from subtranslate.core.translation import TranslationError
from subtranslate.core.subtitle import SubtitleError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def parse_args(args: List[str]) -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='SubtranSlate - Translate subtitle files from one language to another.'
    )
    
    # Input/Output options
    parser.add_argument('input', 
                        help='Input subtitle file or directory containing subtitle files')
    parser.add_argument('output', 
                        help='Output subtitle file or directory to save translated files')
    
    # Language options
    parser.add_argument('--src-lang', '-s', default='en',
                        help='Source language code (default: en)')
    parser.add_argument('--target-lang', '-t', default='zh-CN',
                        help='Target language code (default: zh-CN)')
    
    # Translation options
    parser.add_argument('--mode', choices=['naive', 'split'], default='split',
                        help='Translation mode: naive for simple translation, '
                             'split for more context-aware translation (default: split)')
    parser.add_argument('--both', action='store_true', default=True,
                        help='Include both original and translated text (default: True)')
    parser.add_argument('--only-translation', dest='both', action='store_false',
                        help='Include only translated text')
    parser.add_argument('--space', action='store_true', default=False,
                        help='Target language uses spaces between words (default: False)')
    
    # File options
    parser.add_argument('--encoding', default='UTF-8',
                        help='Input file encoding (default: UTF-8)')
    parser.add_argument('--batch', action='store_true', default=False,
                        help='Process input as directory containing multiple subtitle files')
    parser.add_argument('--pattern', default='*.srt',
                        help='File pattern for batch processing (default: *.srt)')
    
    # API options
    parser.add_argument('--api-key', 
                        help='API key for translation service (optional)')
    parser.add_argument('--service', default='google',
                        help='Translation service to use (default: google)')
    
    # Misc options
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    
    # New option
    parser.add_argument('--no-resume', action='store_true', default=False,
                        help='Do not attempt to resume from previous translations')
    
    return parser.parse_args(args)

def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for the command-line interface.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    if args is None:
        args = sys.argv[1:]
        
    try:
        parsed_args = parse_args(args)
        
        # Configure logging based on verbosity
        if parsed_args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Create translator
        translator = SubtitleTranslator(
            translation_service=parsed_args.service,
            api_key=parsed_args.api_key
        )
        
        # Check if space should be used based on target language
        space = parsed_args.space
        if parsed_args.target_lang in ['fr', 'en', 'de', 'es', 'it', 'pt', 'ru']:
            logger.info(f"Language {parsed_args.target_lang} uses spaces, setting space=True")
            space = True
        
        # Process input/output
        if parsed_args.batch or os.path.isdir(parsed_args.input):
            if not os.path.isdir(parsed_args.input):
                logger.error(f"Input path is not a directory: {parsed_args.input}")
                return 1
                
            logger.info(f"Batch processing files in {parsed_args.input}")
            results = translator.batch_translate_directory(
                input_dir=parsed_args.input,
                output_dir=parsed_args.output,
                src_lang=parsed_args.src_lang,
                target_lang=parsed_args.target_lang,
                file_pattern=parsed_args.pattern,
                encoding=parsed_args.encoding,
                mode=parsed_args.mode,
                both=parsed_args.both,
                space=space,
                resume=not parsed_args.no_resume
            )
            
            # Check results
            success_count = sum(1 for result in results.values() if result["status"] == "success")
            rate_limited_count = sum(1 for result in results.values() if result["status"] == "rate_limited")
            
            logger.info(
                f"Batch translation complete: {success_count}/{len(results)} files successful, "
                f"{rate_limited_count} rate limited"
            )
            
            if success_count == 0:
                logger.error("No files were successfully translated.")
                return 1
        else:
            # Single file processing
            if not os.path.isfile(parsed_args.input):
                logger.error(f"Input file does not exist: {parsed_args.input}")
                return 1
                
            translator.translate_file(
                input_file=parsed_args.input,
                output_file=parsed_args.output,
                src_lang=parsed_args.src_lang,
                target_lang=parsed_args.target_lang,
                encoding=parsed_args.encoding,
                mode=parsed_args.mode,
                both=parsed_args.both,
                space=space,
                resume=not parsed_args.no_resume
            )
            
            logger.info(f"Translation complete: {parsed_args.output}")
        
        return 0
        
    except SubtitleError as e:
        logger.error(f"Subtitle processing error: {e}")
        if parsed_args.verbose:
            traceback.print_exc()
        return 1
    except TranslationError as e:
        logger.error(f"Translation error: {e}")
        if parsed_args.verbose:
            traceback.print_exc()
        return 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main()) 