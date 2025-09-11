"""
Main module for subtitle translation functionality.
"""

import json
import logging
import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from .subtitle import SubtitleError, SubtitleLike, SubtitleProcessor
from .translation import RateLimitError, TranslationError, get_translator

# Type aliases
CheckpointData = Dict[
    str, Union[str, int, float, bool, List[Dict[str, Union[str, int, timedelta, None]]]]
]
SubtitleList = List[SubtitleLike]
BatchResult = Dict[str, str]
BatchResults = Dict[str, BatchResult]

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SubtitleTranslator:
    """Main class for translating subtitles."""

    def __init__(
        self, translation_service: str = "google", api_key: Optional[str] = None
    ):
        """
        Initialize the subtitle translator.

        Args:
            translation_service: Translation service to use
            api_key: API key for the translation service
        """
        self.translator = get_translator(translation_service, api_key)
        self.subtitle_processor = SubtitleProcessor()

    def translate_file(
        self,
        input_file: str,
        output_file: str,
        src_lang: str,
        target_lang: str,
        *,
        encoding: str = "UTF-8",
        mode: str = "split",
        both: bool = True,
        space: bool = False,
        resume: bool = True,
    ) -> None:
        """
        Translate a subtitle file.

        Args:
            input_file: Input subtitle file path
            output_file: Output subtitle file path
            src_lang: Source language code
            target_lang: Target language code
            encoding: File encoding
            mode: Translation mode ('naive' or 'split')
            both: Whether to keep original text
            space: Whether the target language uses spaces
            resume: Whether to attempt resuming from a previous checkpoint

        Raises:
            SubtitleError: If subtitle processing fails
            TranslationError: If translation fails
        """
        logger.info("Translating %s from %s to %s", input_file, src_lang, target_lang)
        start_time = time.time()

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Check for checkpoint file
        checkpoint_file = f"{output_file}.checkpoint"
        checkpoint_data = None

        if resume and os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, "r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)

                logger.info(
                    "Found checkpoint file with %d%% completion",
                    checkpoint_data.get("progress", 0),
                )

                # If the checkpoint is complete, we can use the output file directly
                if checkpoint_data.get("status") == "complete":
                    logger.info(
                        "Translation was already completed according to checkpoint"
                    )
                    return

            except (OSError, IOError, json.JSONDecodeError) as e:
                logger.warning("Failed to load checkpoint file: %s", e)
                checkpoint_data = None

        # Parse subtitle file (or load from checkpoint)
        subtitles = None
        if checkpoint_data and "parsed_subtitles" in checkpoint_data:
            try:
                subtitles = self.subtitle_processor.from_serialized(
                    checkpoint_data["parsed_subtitles"]
                )
                logger.info(
                    "Loaded %d subtitle entries from checkpoint", len(subtitles)
                )
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(
                    "Failed to load subtitles from checkpoint: %s, will reparse file", e
                )
                subtitles = None

        if subtitles is None:
            try:
                subtitles = self.subtitle_processor.parse_file(input_file, encoding)
                logger.info("Parsed %d subtitle entries", len(subtitles))
            except SubtitleError as e:
                logger.error("Failed to parse subtitle file: %s", e)
                raise

            # Create initial checkpoint
            if resume:
                self._save_checkpoint(
                    checkpoint_file,
                    {
                        "status": "parsing_complete",
                        "input_file": input_file,
                        "output_file": output_file,
                        "src_lang": src_lang,
                        "target_lang": target_lang,
                        "mode": mode,
                        "both": both,
                        "progress": 0,
                        "parsed_subtitles": self.subtitle_processor.to_serialized(
                            subtitles
                        ),
                    },
                )

        # Translate subtitles
        translated_subtitles = None

        # If we have partial translations in the checkpoint, use them
        if checkpoint_data and "partial_translation" in checkpoint_data:
            try:
                translated_subtitles = checkpoint_data["partial_translation"]
                logger.info(
                    "Resuming translation from checkpoint at %d%% completion",
                    checkpoint_data.get("progress", 0),
                )
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(
                    "Failed to use partial translation from checkpoint: %s", e
                )
                translated_subtitles = None

        # Translate from scratch if needed
        if translated_subtitles is None:
            try:
                if mode == "naive":
                    translated_subtitles = self._translate_naive(
                        subtitles,
                        src_lang,
                        target_lang,
                        both=both,
                        checkpoint_file=checkpoint_file if resume else None,
                    )
                else:
                    translated_subtitles = self._translate_split(
                        subtitles,
                        src_lang,
                        target_lang,
                        both=both,
                        space=space,
                        checkpoint_file=checkpoint_file if resume else None,
                    )
            except (SubtitleError, TranslationError, RateLimitError) as e:
                logger.error("Translation failed: %s", e)
                raise

        # Save translated subtitles
        try:
            self.subtitle_processor.save_file(
                translated_subtitles, output_file, encoding="UTF-8"
            )
        except SubtitleError as e:
            logger.error("Failed to save subtitle file: %s", e)
            raise

        # Update checkpoint to mark as complete
        if resume and os.path.exists(checkpoint_file):
            self._save_checkpoint(
                checkpoint_file,
                {
                    "status": "complete",
                    "input_file": input_file,
                    "output_file": output_file,
                    "progress": 100,
                },
            )

        elapsed_time = time.time() - start_time
        logger.info("Translation completed in %.2f seconds", elapsed_time)

    def _save_checkpoint(self, checkpoint_file: str, data: CheckpointData) -> None:
        """Save translation progress to checkpoint file."""
        try:
            # Create a custom JSON encoder to handle timedelta objects
            class CustomJSONEncoder(json.JSONEncoder):
                """Custom JSON encoder for handling timedelta objects."""

                def default(self, o: object) -> str:
                    if isinstance(o, timedelta):
                        return str(o)
                    # super().default() raises TypeError if object is not serializable
                    # but mypy thinks it returns Any, so we cast the result
                    result = super().default(o)
                    return str(result)

            with open(checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            logger.debug("Saved checkpoint to %s", checkpoint_file)
        except (OSError, IOError, TypeError) as e:
            logger.warning("Failed to save checkpoint: %s", e)

    def _translate_naive(
        self,
        subtitles: SubtitleList,
        src_lang: str,
        target_lang: str,
        *,
        both: bool = True,
        checkpoint_file: Optional[str] = None,
    ) -> SubtitleList:
        """
        Translate subtitles in 'naive' mode (straightforward translation).

        Args:
            subtitles: List of subtitle objects
            src_lang: Source language code
            target_lang: Target language code
            both: Whether to keep original text
            checkpoint_file: Path to checkpoint file for resuming

        Returns:
            List of translated subtitle objects
        """
        logger.info("Using naive translation mode")

        # Extract text content from subtitles
        content_list = [sub.content.replace("\n", "") for sub in subtitles]

        try:
            # Translate the content with progress reporting
            translated_text = None

            for retry_count in range(3):  # Allow a few retries for the entire batch
                try:
                    # Translate with progress tracking
                    translated_text = self._translate_with_progress(
                        content_list,
                        src_lang,
                        target_lang,
                        checkpoint_file=checkpoint_file,
                        mode="naive",
                    )
                    break
                except RateLimitError:
                    if retry_count < 2:  # Only retry twice
                        backoff_time = 60 * (retry_count + 1)  # 60s, 120s
                        logger.warning(
                            "Rate limit detected. Backing off for %ds before retry %d/3",
                            backoff_time,
                            retry_count + 1,
                        )
                        time.sleep(backoff_time)
                    else:
                        logger.error("Max retries reached after rate limiting")
                        raise

            if translated_text is None:
                raise TranslationError("Failed to translate content after retries")

            translated_list = translated_text.split("\n")

            # Handle potential mismatch in lists length
            if len(translated_list) != len(subtitles):
                logger.warning(
                    "Subtitle count mismatch: %d vs %d",
                    len(subtitles),
                    len(translated_list),
                )
                # Try to fix by padding or truncating
                if len(translated_list) < len(subtitles):
                    translated_list.extend(
                        [""] * (len(subtitles) - len(translated_list))
                    )
                else:
                    translated_list = translated_list[: len(subtitles)]

            # Apply translations to subtitle objects
            result = self.subtitle_processor.simple_translate_subtitles(
                subtitles, translated_list, both
            )

            # Save full completion to checkpoint
            if checkpoint_file:
                self._save_checkpoint(
                    checkpoint_file,
                    {
                        "status": "translation_complete",
                        "progress": 100,
                        "mode": "naive",
                    },
                )

            return result

        except Exception as e:
            logger.error("Failed in naive translation mode: %s", e)
            raise

    def _translate_with_progress(
        self,
        text_list: List[str],
        src_lang: str,
        target_lang: str,
        *,
        checkpoint_file: Optional[str] = None,
        mode: str = "split",
    ) -> str:
        """
        Translate a list of texts while tracking progress and handling checkpoints.

        Args:
            text_list: List of texts to translate
            src_lang: Source language code
            target_lang: Target language code
            checkpoint_file: Path to checkpoint file
            mode: Translation mode ('naive' or 'split')

        Returns:
            Translated text
        """
        if not text_list:
            return ""

        # Report progress periodically
        last_progress_report = time.time()
        progress_interval = 5  # seconds

        # Delegate to the translator with progress callback
        def progress_callback(current: int, total: int, translated_so_far: str) -> None:
            nonlocal last_progress_report

            # Calculate progress percentage
            progress = (current / total) * 100 if total > 0 else 0

            # Report progress and update checkpoint periodically
            now = time.time()
            if now - last_progress_report >= progress_interval:
                logger.info(
                    "Translation progress: %.1f%% (%d/%d)", progress, current, total
                )
                last_progress_report = now

                # Update checkpoint with partial progress
                if checkpoint_file:
                    self._save_checkpoint(
                        checkpoint_file,
                        {
                            "status": "translating",
                            "progress": progress,
                            "current_index": current,
                            "total_items": total,
                            "mode": mode,
                            "partial_translation": translated_so_far,
                        },
                    )

        # Use the translator with progress tracking
        try:
            return self.translator.translate_lines(
                text_list, src_lang, target_lang, progress_callback
            )
        except Exception as e:
            logger.error("Translation with progress tracking failed: %s", e)
            raise

    def _translate_split(
        self,
        subtitles: SubtitleList,
        src_lang: str,
        target_lang: str,
        *,
        both: bool = True,
        space: bool = False,
        checkpoint_file: Optional[str] = None,
    ) -> SubtitleList:
        """
        Translate subtitles in 'split' mode (more advanced, context-aware translation).

        Args:
            subtitles: List of subtitle objects
            src_lang: Source language code
            target_lang: Target language code
            both: Whether to keep original text
            space: Whether the target language uses spaces
            checkpoint_file: Path to checkpoint file for resuming

        Returns:
            List of translated subtitle objects
        """
        logger.info("Using split translation mode")

        # Process subtitles
        plain_text, dialog_idx = self.subtitle_processor.triple_r(subtitles)
        sen_list, sen_idx = self.subtitle_processor.split_and_record(plain_text)

        logger.info("Split into %d sentences", len(sen_list))

        try:
            # Translate the sentences with progress reporting
            translated_sen = None

            for retry_count in range(3):  # Allow a few retries for the entire batch
                try:
                    # Translate with progress tracking
                    translated_sen = self._translate_with_progress(
                        sen_list,
                        src_lang,
                        target_lang,
                        checkpoint_file=checkpoint_file,
                        mode="split",
                    )
                    break
                except RateLimitError:
                    if retry_count < 2:  # Only retry twice
                        backoff_time = 60 * (retry_count + 1)  # 60s, 120s
                        logger.warning(
                            "Rate limit detected. Backing off for %ds before retry %d/3",
                            backoff_time,
                            retry_count + 1,
                        )
                        time.sleep(backoff_time)
                    else:
                        logger.error("Max retries reached after rate limiting")
                        raise

            if translated_sen is None:
                raise TranslationError("Failed to translate sentences after retries")

            translated_sen_list = translated_sen.split("\n")

            # Handle potential mismatch in lengths
            if len(translated_sen_list) != len(sen_list):
                logger.warning(
                    "Sentence count mismatch after translation: %d vs %d",
                    len(sen_list),
                    len(translated_sen_list),
                )
                # Try to fix by padding or truncating
                if len(translated_sen_list) < len(sen_list):
                    translated_sen_list.extend(
                        [""] * (len(sen_list) - len(translated_sen_list))
                    )
                else:
                    translated_sen_list = translated_sen_list[: len(sen_list)]

            # Compute mapping and convert sentences to dialogues
            mass_list = self.subtitle_processor.compute_mass_list(dialog_idx, sen_idx)

            # Special handling for Chinese
            is_chinese = target_lang in ("zh-CN", "zh-TW")
            dialog_list = self.subtitle_processor.sen_list2dialog_list(
                translated_sen_list, mass_list, space, is_chinese=is_chinese
            )

            # Apply translations to subtitle objects
            result = self.subtitle_processor.advanced_translate_subtitles(
                subtitles, dialog_list, both
            )

            # Save full completion to checkpoint
            if checkpoint_file:
                self._save_checkpoint(
                    checkpoint_file,
                    {
                        "status": "translation_complete",
                        "progress": 100,
                        "mode": "split",
                    },
                )

            return result

        except Exception as e:
            logger.error("Failed in split translation mode: %s", e)
            raise

    def batch_translate_directory(
        self,
        input_dir: str,
        output_dir: str,
        src_lang: str,
        target_lang: str,
        *,
        file_pattern: str = "*.srt",
        encoding: str = "UTF-8",
        mode: str = "split",
        both: bool = True,
        space: bool = False,
        resume: bool = True,
    ) -> BatchResults:
        """
        Translate all subtitle files in a directory.

        Args:
            input_dir: Directory containing subtitle files
            output_dir: Directory to save translated files
            src_lang: Source language code
            target_lang: Target language code
            file_pattern: Pattern to match subtitle files
            encoding: File encoding
            mode: Translation mode
            both: Whether to keep original text
            space: Whether the target language uses spaces
            resume: Whether to resume previous translations

        Returns:
            Dictionary mapping input files to output files with status
        """
        if not os.path.isdir(input_dir):
            raise ValueError(f"Input directory does not exist: {input_dir}")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Find all SRT files in the input directory
        input_files = list(Path(input_dir).glob(file_pattern))
        logger.info("Found %d subtitle files to translate", len(input_files))

        # Check for batch state file
        batch_state_file = os.path.join(
            output_dir, f"batch_state_{src_lang}_{target_lang}.json"
        )
        batch_state = {}

        if resume and os.path.exists(batch_state_file):
            try:
                with open(batch_state_file, "r", encoding="utf-8") as f:
                    batch_state = json.load(f)
                logger.info("Loaded batch state with %d files", len(batch_state))
            except (OSError, IOError, json.JSONDecodeError) as e:
                logger.warning("Failed to load batch state: %s", e)
                batch_state = {}

        results = {}
        for input_file in input_files:
            input_path = str(input_file)
            file_name = os.path.basename(input_path)

            # Generate output file name
            lang_suffix = f"_{src_lang}_{target_lang}"
            if both:
                lang_suffix += "_both"
            else:
                lang_suffix += "_only"

            output_name = f"{os.path.splitext(file_name)[0]}{lang_suffix}.srt"
            output_path = os.path.join(output_dir, output_name)

            # Skip completed files if resume is enabled
            if (
                resume
                and input_path in batch_state
                and batch_state[input_path].get("status") == "success"
            ):
                logger.info(
                    "Skipping %s (already completed according to batch state)",
                    input_path,
                )
                results[input_path] = batch_state[input_path]
                continue

            try:
                self.translate_file(
                    input_path,
                    output_path,
                    src_lang,
                    target_lang,
                    encoding=encoding,
                    mode=mode,
                    both=both,
                    space=space,
                    resume=resume,
                )
                results[input_path] = {"status": "success", "output": output_path}
                logger.info("Successfully translated %s to %s", input_path, output_path)

                # Update batch state
                if resume:
                    batch_state[input_path] = results[input_path]
                    with open(batch_state_file, "w", encoding="utf-8") as f:
                        json.dump(batch_state, f, ensure_ascii=False, indent=2)

            except RateLimitError as e:
                # Special handling for rate limiting - record the error but continue with
                # next file after a pause
                results[input_path] = {
                    "status": "rate_limited",
                    "message": str(e),
                    "output": output_path,
                }
                logger.error("Rate limited when translating %s: %s", input_path, e)
                logger.info("Pausing for 2 minutes before continuing with next file")
                time.sleep(120)  # 2 minute pause before trying the next file

                # Update batch state
                if resume:
                    batch_state[input_path] = results[input_path]
                    with open(batch_state_file, "w", encoding="utf-8") as f:
                        json.dump(batch_state, f, ensure_ascii=False, indent=2)

            except (SubtitleError, TranslationError, OSError, IOError) as e:
                results[input_path] = {"status": "error", "message": str(e)}
                logger.error("Failed to translate %s: %s", input_path, e)

                # Update batch state
                if resume:
                    batch_state[input_path] = results[input_path]
                    with open(batch_state_file, "w", encoding="utf-8") as f:
                        json.dump(batch_state, f, ensure_ascii=False, indent=2)

        # Log summary
        success_count = sum(
            1 for result in results.values() if result["status"] == "success"
        )
        rate_limited_count = sum(
            1 for result in results.values() if result["status"] == "rate_limited"
        )
        logger.info(
            "Translation complete: %d/%d files successful, %d rate limited",
            success_count,
            len(input_files),
            rate_limited_count,
        )

        return results


def translate_and_compose(
    input_file: str,
    output_file: str,
    src_lang: str,
    target_lang: str,
    *,
    encoding: str = "UTF-8",
    mode: str = "split",
    both: bool = True,
    space: bool = False,
    api_key: Optional[str] = None,
    resume: bool = True,
) -> None:
    """
    Translate subtitle file (simple interface function).

    Args:
        input_file: Input subtitle file path
        output_file: Output subtitle file path
        src_lang: Source language code
        target_lang: Target language code
        encoding: File encoding
        mode: Translation mode ('naive' or 'split')
        both: Whether to keep original text
        space: Whether the target language uses spaces
        api_key: API key for the translation service
        resume: Whether to attempt resuming from a previous checkpoint
    """
    translator = SubtitleTranslator(api_key=api_key)
    translator.translate_file(
        input_file,
        output_file,
        src_lang,
        target_lang,
        encoding=encoding,
        mode=mode,
        both=both,
        space=space,
        resume=resume,
    )
