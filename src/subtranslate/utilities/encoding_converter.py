"""
Subtitle file encoding conversion utility.

This module provides functionality to convert subtitle files between different encodings
commonly used for subtitles in various languages and regions.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Common encodings for subtitles
COMMON_ENCODINGS = [
    "utf-8",
    "utf-8-sig",  # UTF-8 with BOM
    "cp874",  # Windows Thai
    "tis-620",  # Thai Industrial Standard
    "iso8859-11",  # ISO Latin/Thai
    "cp1250",  # Windows Central European
    "cp1251",  # Windows Cyrillic
    "cp1252",  # Windows Western European
    "cp1253",  # Windows Greek
    "cp1254",  # Windows Turkish
    "cp1255",  # Windows Hebrew
    "cp1256",  # Windows Arabic
    "cp1257",  # Windows Baltic
    "cp1258",  # Windows Vietnamese
    "cp932",  # Windows Japanese
    "cp936",  # Windows Simplified Chinese
    "cp949",  # Windows Korean
    "cp950",  # Windows Traditional Chinese
    "euc-jp",  # Japanese
    "euc-kr",  # Korean
    "shift_jis",  # Japanese
    "gb2312",  # Simplified Chinese
    "big5",  # Traditional Chinese
    "iso8859-1",  # Western European
    "iso8859-2",  # Central European
    "iso8859-3",  # South European
    "iso8859-4",  # North European
    "iso8859-5",  # Cyrillic
    "iso8859-6",  # Arabic
    "iso8859-7",  # Greek
    "iso8859-8",  # Hebrew
    "iso8859-9",  # Turkish
    "iso8859-10",  # Nordic
    "iso8859-13",  # Baltic
    "iso8859-14",  # Celtic
    "iso8859-15",  # Western European with Euro
    "iso8859-16",  # South-Eastern European
]


def detect_encoding(
    file_path: str, encodings_to_try: Optional[List[str]] = None
) -> Optional[str]:
    """
    Attempt to detect the encoding of a subtitle file by trying multiple encodings.

    Args:
        file_path: Path to the subtitle file
        encodings_to_try: List of encodings to try, defaults to COMMON_ENCODINGS

    Returns:
        Detected encoding or None if detection fails
    """
    if encodings_to_try is None:
        encodings_to_try = COMMON_ENCODINGS

    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return None

    for encoding_name in encodings_to_try:
        try:
            with open(file_path, "r", encoding=encoding_name) as f:
                content = f.read()
                # If we can read at least 100 characters without error,
                # it's probably the right encoding
                if len(content) > 100:
                    logger.debug("Detected encoding: %s", encoding_name)
                    return encoding_name
        except UnicodeDecodeError:
            continue
        except (OSError, IOError) as e:
            logger.debug("Error trying encoding %s: %s", encoding_name, e)
            continue

    logger.error("Could not detect encoding for %s", file_path)
    return None


def convert_subtitle_encoding(
    input_file: str,
    output_file: str,
    target_encoding: str,
    source_encoding: Optional[str] = None,
) -> bool:
    """
    Convert subtitle file from source encoding to target encoding.

    Args:
        input_file: Path to the input subtitle file
        output_file: Path to save the converted subtitle file
        target_encoding: Target encoding to convert to
        source_encoding: Source encoding of input file (auto-detect if None)

    Returns:
        True if conversion was successful, False otherwise
    """
    try:
        # Determine source encoding if not provided
        if source_encoding is None:
            source_encoding = detect_encoding(input_file)
            if source_encoding is None:
                return False

        # Read the source file
        with open(input_file, "r", encoding=source_encoding) as f:
            content = f.read()

        # Write with target encoding
        with open(output_file, "wb") as f:
            # Add BOM if target is UTF-8 with BOM
            if target_encoding.lower() == "utf-8-sig":
                f.write(b"\xef\xbb\xbf")  # UTF-8 BOM
                f.write(content.encode("utf-8", errors="replace"))
            else:
                f.write(content.encode(target_encoding, errors="replace"))

        logger.info(
            "Converted %s from %s to %s -> %s",
            input_file,
            source_encoding,
            target_encoding,
            output_file,
        )
        return True
    except (OSError, IOError, UnicodeError, LookupError) as e:
        logger.error("Error converting %s to %s: %s", input_file, target_encoding, e)
        return False


def convert_to_multiple_encodings(
    input_file: str,
    output_dir: Optional[str] = None,
    target_encodings: Optional[List[str]] = None,
) -> Dict[str, bool]:
    """
    Convert a subtitle file to multiple encodings.

    Args:
        input_file: Path to the input subtitle file
        output_dir: Directory to save converted files (defaults to input file directory)
        target_encodings: List of target encodings (defaults to a common subset)

    Returns:
        Dictionary mapping target encodings to conversion success status
    """
    if target_encodings is None:
        target_encodings = ["utf-8", "utf-8-sig", "cp874", "tis-620", "iso8859-11"]

    if not os.path.exists(input_file):
        logger.error("Input file not found: %s", input_file)
        return {encoding: False for encoding in target_encodings}

    if output_dir is None:
        output_dir = os.path.dirname(input_file) or "."

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Determine source file details
    source_path = Path(input_file)
    source_encoding = detect_encoding(input_file)
    if source_encoding is None:
        return {encoding: False for encoding in target_encodings}

    results = {}
    for target_encoding in target_encodings:
        # Create output filename with encoding as suffix
        stem = source_path.stem
        # Remove any existing encoding suffix
        for common_enc in COMMON_ENCODINGS:
            suffix = f"-{common_enc}"
            if stem.lower().endswith(suffix.lower()):
                stem = stem[: -len(suffix)]

        output_file = os.path.join(
            output_dir, f"{stem}-{target_encoding}{source_path.suffix}"
        )

        # Skip if the target encoding matches the source
        if target_encoding.lower() == source_encoding.lower() and os.path.samefile(
            input_file, output_file
        ):
            logger.info(
                "Skipping conversion to %s as it matches source encoding",
                target_encoding,
            )
            results[target_encoding] = True
            continue

        # Convert the file
        conversion_success = convert_subtitle_encoding(
            input_file, output_file, target_encoding, source_encoding
        )
        results[target_encoding] = conversion_success

    return results


def get_recommended_encodings(language_code: str) -> List[str]:
    """
    Get recommended encodings for a specific language.

    Args:
        language_code: ISO language code (e.g., 'th', 'zh-CN', 'ja')

    Returns:
        List of recommended encodings for the language
    """
    # Map of language codes to recommended encodings (most preferred first)
    language_encodings = {
        "th": ["utf-8", "tis-620", "cp874", "iso8859-11"],  # Thai
        "zh-CN": ["utf-8", "gb2312", "cp936"],  # Simplified Chinese
        "zh-TW": ["utf-8", "big5", "cp950"],  # Traditional Chinese
        "ja": ["utf-8", "shift_jis", "euc-jp", "cp932"],  # Japanese
        "ko": ["utf-8", "euc-kr", "cp949"],  # Korean
        "ru": ["utf-8", "cp1251", "koi8-r", "iso8859-5"],  # Russian
        "ar": ["utf-8", "cp1256", "iso8859-6"],  # Arabic
        "he": ["utf-8", "cp1255", "iso8859-8"],  # Hebrew
        "tr": ["utf-8", "cp1254", "iso8859-9"],  # Turkish
        "el": ["utf-8", "cp1253", "iso8859-7"],  # Greek
        "vi": ["utf-8", "cp1258"],  # Vietnamese
    }

    # Default to UTF-8 and common Western encodings
    default_encodings = ["utf-8", "utf-8-sig", "cp1252", "iso8859-1", "iso8859-15"]

    # Get language code without region
    base_lang = language_code.split("-")[0]

    # Return recommended encodings or default
    return language_encodings.get(
        language_code, language_encodings.get(base_lang, default_encodings)
    )


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python encoding_converter.py input_file [output_dir] [encoding1,encoding2,...]"
        )
        sys.exit(1)

    input_file_path = sys.argv[1]
    output_directory = sys.argv[2] if len(sys.argv) > 2 else None

    if len(sys.argv) > 3:
        encodings = sys.argv[3].split(",")
    else:
        # Default to some common encodings
        encodings = ["utf-8", "utf-8-sig", "cp874", "tis-620"]

    conversion_results = convert_to_multiple_encodings(
        input_file_path, output_directory, target_encodings=encodings
    )

    for encoding, success in conversion_results.items():
        STATUS = "Success" if success else "Failed"
        print(f"{encoding}: {STATUS}")
