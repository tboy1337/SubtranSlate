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

from src.subtranslate.core.main import SubtitleTranslator
from src.subtranslate.core.translation import TranslationError
from src.subtranslate.core.subtitle import SubtitleError
from src.subtranslate.utilities.encoding_converter import (
    convert_subtitle_encoding,
    convert_to_multiple_encodings,
    detect_encoding,
    get_recommended_encodings,
    COMMON_ENCODINGS
)

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
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Translate command
    translate_parser = subparsers.add_parser('translate', help='Translate subtitle files')
    
    # Input/Output options
    translate_parser.add_argument('input', 
                        help='Input subtitle file or directory containing subtitle files')
    translate_parser.add_argument('output', 
                        help='Output subtitle file or directory to save translated files')
    
    # Language options
    translate_parser.add_argument('--src-lang', '-s', default='en',
                        help='Source language code (default: en)')
    translate_parser.add_argument('--target-lang', '-t', default='zh-CN',
                        help='Target language code (default: zh-CN)')
    
    # Translation options
    translate_parser.add_argument('--mode', choices=['naive', 'split'], default='split',
                        help='Translation mode: naive for simple translation, '
                             'split for more context-aware translation (default: split)')
    translate_parser.add_argument('--both', action='store_true', default=True,
                        help='Include both original and translated text (default: True)')
    translate_parser.add_argument('--only-translation', dest='both', action='store_false',
                        help='Include only translated text')
    translate_parser.add_argument('--space', action='store_true', default=False,
                        help='Target language uses spaces between words (default: False)')
    
    # File options
    translate_parser.add_argument('--encoding', default='UTF-8',
                        help='Input file encoding (default: UTF-8)')
    translate_parser.add_argument('--batch', action='store_true', default=False,
                        help='Process input as directory containing multiple subtitle files')
    translate_parser.add_argument('--pattern', default='*.srt',
                        help='File pattern for batch processing (default: *.srt)')
    
    # API options
    translate_parser.add_argument('--api-key', 
                        help='API key for translation service (optional)')
    translate_parser.add_argument('--service', default='google',
                        help='Translation service to use (default: google)')
    
    # Misc options
    translate_parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    
    # New option
    translate_parser.add_argument('--no-resume', action='store_true', default=False,
                        help='Do not attempt to resume from previous translations')

    # Encoding conversion command
    encode_parser = subparsers.add_parser('encode', help='Convert subtitle file encodings')
    
    # Create a mutually exclusive group for non-file operations
    encode_non_file_group = encode_parser.add_argument_group('Non-file operations')
    encode_non_file_group.add_argument('--list-encodings', action='store_true',
                      help='List all supported encodings and exit')
    
    # Input/Output options
    encode_parser.add_argument('input', nargs='?',
                      help='Input subtitle file or directory containing subtitle files')
    encode_parser.add_argument('--output-dir', '-o',
                      help='Output directory to save converted files (defaults to input directory)')
    
    # Encoding options
    encode_parser.add_argument('--from-encoding', '-f',
                      help='Source encoding of the input file (auto-detect if not specified)')
    encode_parser.add_argument('--to-encoding', '-t',
                      help='Target encoding to convert to (can specify multiple with comma separation)')
    encode_parser.add_argument('--all', '-a', action='store_true',
                      help='Convert to all common subtitle encodings')
    encode_parser.add_argument('--recommended', '-r', action='store_true',
                      help='Convert to recommended encodings based on language')
    encode_parser.add_argument('--language', '-l', default='en',
                      help='Language code for recommended encodings (e.g., th, zh-CN, ja)')
    
    # File options
    encode_parser.add_argument('--batch', action='store_true',
                      help='Process input as directory containing multiple subtitle files')
    encode_parser.add_argument('--pattern', default='*.srt',
                      help='File pattern for batch processing (default: *.srt)')
    
    # Misc options
    encode_parser.add_argument('--verbose', '-v', action='store_true',
                      help='Enable verbose logging')
    
    # For backwards compatibility, if no command is specified, default to 'translate'
    if len(args) > 0 and args[0] not in ['translate', 'encode']:
        args = ['translate'] + args
    
    # First parse the args to see if we have --list-encodings
    temp_args, _ = parser.parse_known_args(args)
    
    # Custom parsing for special cases
    parsed_args = parser.parse_args(args)
    
    # Validate arguments based on command
    if parsed_args.command == 'encode':
        # If listing encodings, input is not required
        if parsed_args.list_encodings:
            return parsed_args
        # Otherwise, input is required
        if not parsed_args.input:
            encode_parser.error("the following arguments are required: input")
    
    return parsed_args

def handle_encoding_command(args: argparse.Namespace) -> int:
    """
    Handle the encoding conversion command.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Configure logging based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # List encodings if requested
    if args.list_encodings:
        print("Supported encodings:")
        for encoding in COMMON_ENCODINGS:
            print(f"  {encoding}")
        return 0
    
    # Determine target encodings
    target_encodings = []
    
    if args.to_encoding:
        target_encodings = [enc.strip() for enc in args.to_encoding.split(',')]
    
    if args.recommended:
        target_encodings = get_recommended_encodings(args.language)
        logger.info(f"Using recommended encodings for {args.language}: {', '.join(target_encodings)}")
    
    if args.all:
        target_encodings = COMMON_ENCODINGS
        logger.info(f"Converting to all {len(target_encodings)} supported encodings")
    
    if not target_encodings:
        # Default to some common encodings
        target_encodings = ['utf-8', 'utf-8-sig', 'tis-620', 'cp874']
        logger.info(f"No target encoding specified, using defaults: {', '.join(target_encodings)}")
    
    # Process input path
    if args.batch or os.path.isdir(args.input):
        if not os.path.isdir(args.input):
            logger.error(f"Input path is not a directory: {args.input}")
            return 1
            
        # Batch processing
        import glob
        
        input_dir = args.input
        output_dir = args.output_dir or input_dir
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Find all subtitle files
        pattern = os.path.join(input_dir, args.pattern)
        subtitle_files = glob.glob(pattern)
        
        if not subtitle_files:
            logger.error(f"No files matching pattern '{args.pattern}' found in {input_dir}")
            return 1
            
        logger.info(f"Found {len(subtitle_files)} subtitle files to process")
        
        # Process each file
        results = {}
        for file_path in subtitle_files:
            rel_path = os.path.relpath(file_path, input_dir)
            file_output_dir = os.path.join(output_dir, os.path.dirname(rel_path))
            
            # Create output subdirectory if needed
            if not os.path.exists(file_output_dir):
                os.makedirs(file_output_dir)
                
            # Convert the file
            file_results = convert_to_multiple_encodings(
                file_path,
                file_output_dir,
                target_encodings
            )
            results[rel_path] = file_results
        
        # Print summary
        print("\nConversion summary:")
        for file_path, encodings in results.items():
            print(f"\n{file_path}:")
            for encoding, success in encodings.items():
                status = "Success" if success else "Failed"
                print(f"  {encoding}: {status}")
                
        # Count successes
        total_conversions = sum(len(encodings) for encodings in results.values())
        successful_conversions = sum(
            sum(1 for success in encodings.values() if success)
            for encodings in results.values()
        )
        
        if successful_conversions == 0:
            logger.error("No files were successfully converted.")
            return 1
            
        logger.info(f"Converted {successful_conversions}/{total_conversions} files successfully")
        return 0
    else:
        # Single file processing
        if not os.path.isfile(args.input):
            logger.error(f"Input file does not exist: {args.input}")
            return 1
            
        output_dir = args.output_dir or os.path.dirname(args.input) or '.'
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Check source encoding
        source_encoding = args.from_encoding
        if not source_encoding:
            detected = detect_encoding(args.input)
            if detected:
                source_encoding = detected
                logger.info(f"Detected source encoding: {source_encoding}")
            else:
                logger.error(f"Could not detect encoding of {args.input}")
                return 1
        
        # Convert to each target encoding
        results = {}
        for encoding in target_encodings:
            # Create output path
            input_path = Path(args.input)
            stem = input_path.stem
            # Remove any existing encoding suffix
            for enc in COMMON_ENCODINGS:
                suffix = f"-{enc}"
                if stem.lower().endswith(suffix.lower()):
                    stem = stem[:-len(suffix)]
                    
            output_file = os.path.join(output_dir, f"{stem}-{encoding}{input_path.suffix}")
            
            # Convert the file
            success = convert_subtitle_encoding(args.input, output_file, encoding, source_encoding)
            results[encoding] = success
            
        # Print summary
        print("\nConversion results:")
        for encoding, success in results.items():
            status = "Success" if success else "Failed"
            print(f"  {encoding}: {status}")
            
        # Check if any conversions were successful
        if not any(results.values()):
            logger.error("All conversions failed.")
            return 1
            
        return 0

def handle_translate_command(args: argparse.Namespace) -> int:
    """
    Handle the translate command.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Configure logging based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create translator
    translator = SubtitleTranslator(
        translation_service=args.service,
        api_key=args.api_key
    )
    
    # Check if space should be used based on target language
    space = args.space
    if args.target_lang in ['fr', 'en', 'de', 'es', 'it', 'pt', 'ru']:
        logger.info(f"Language {args.target_lang} uses spaces, setting space=True")
        space = True
    
    # Process input/output
    if args.batch or os.path.isdir(args.input):
        if not os.path.isdir(args.input):
            logger.error(f"Input path is not a directory: {args.input}")
            return 1
            
        logger.info(f"Batch processing files in {args.input}")
        results = translator.batch_translate_directory(
            input_dir=args.input,
            output_dir=args.output,
            src_lang=args.src_lang,
            target_lang=args.target_lang,
            file_pattern=args.pattern,
            encoding=args.encoding,
            mode=args.mode,
            both=args.both,
            space=space,
            resume=not args.no_resume
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
        if not os.path.isfile(args.input):
            logger.error(f"Input file does not exist: {args.input}")
            return 1
            
        translator.translate_file(
            input_file=args.input,
            output_file=args.output,
            src_lang=args.src_lang,
            target_lang=args.target_lang,
            encoding=args.encoding,
            mode=args.mode,
            both=args.both,
            space=space,
            resume=not args.no_resume
        )
        
        logger.info(f"Translation complete: {args.output}")
    
    return 0

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
        
        # Dispatch to appropriate handler based on command
        if parsed_args.command == 'encode':
            return handle_encoding_command(parsed_args)
        else:  # Default to 'translate'
            return handle_translate_command(parsed_args)
            
    except SubtitleError as e:
        logger.error(f"Subtitle processing error: {e}")
        if hasattr(parsed_args, 'verbose') and parsed_args.verbose:
            traceback.print_exc()
        return 1
    except TranslationError as e:
        logger.error(f"Translation error: {e}")
        if hasattr(parsed_args, 'verbose') and parsed_args.verbose:
            traceback.print_exc()
        return 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 