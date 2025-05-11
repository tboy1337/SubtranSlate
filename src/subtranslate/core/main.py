"""
Main module for subtitle translation functionality.
"""

import os
import logging
import json
from typing import List, Optional, Dict, Any
import time
from pathlib import Path

from .translation import get_translator, TranslationError, RateLimitError
from .subtitle import SubtitleProcessor, SubtitleError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class SubtitleTranslator:
    """Main class for translating subtitles."""
    
    def __init__(self, translation_service: str = "google", api_key: Optional[str] = None):
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
        encoding: str = 'UTF-8',
        mode: str = 'split',
        both: bool = True,
        space: bool = False,
        resume: bool = True
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
        logger.info(f"Translating {input_file} from {src_lang} to {target_lang}")
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
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)
                    
                logger.info(f"Found checkpoint file with {checkpoint_data.get('progress', 0)}% completion")
                
                # If the checkpoint is complete, we can use the output file directly
                if checkpoint_data.get('status') == 'complete':
                    logger.info(f"Translation was already completed according to checkpoint")
                    return
                    
            except Exception as e:
                logger.warning(f"Failed to load checkpoint file: {e}")
                checkpoint_data = None
        
        # Parse subtitle file (or load from checkpoint)
        subtitles = None
        if checkpoint_data and 'parsed_subtitles' in checkpoint_data:
            try:
                subtitles = self.subtitle_processor.from_serialized(checkpoint_data['parsed_subtitles'])
                logger.info(f"Loaded {len(subtitles)} subtitle entries from checkpoint")
            except Exception as e:
                logger.warning(f"Failed to load subtitles from checkpoint: {e}, will reparse file")
                subtitles = None
                
        if subtitles is None:
            try:
                subtitles = self.subtitle_processor.parse_file(input_file, encoding)
                logger.info(f"Parsed {len(subtitles)} subtitle entries")
            except SubtitleError as e:
                logger.error(f"Failed to parse subtitle file: {e}")
                raise
            
            # Create initial checkpoint
            if resume:
                self._save_checkpoint(checkpoint_file, {
                    'status': 'parsing_complete',
                    'input_file': input_file,
                    'output_file': output_file,
                    'src_lang': src_lang,
                    'target_lang': target_lang,
                    'mode': mode,
                    'both': both,
                    'progress': 0,
                    'parsed_subtitles': self.subtitle_processor.to_serialized(subtitles)
                })
        
        # Translate subtitles
        translated_subtitles = None
        
        # If we have partial translations in the checkpoint, use them
        if checkpoint_data and 'partial_translation' in checkpoint_data:
            try:
                translated_subtitles = checkpoint_data['partial_translation']
                logger.info(f"Resuming translation from checkpoint at {checkpoint_data.get('progress', 0)}% completion")
            except Exception as e:
                logger.warning(f"Failed to use partial translation from checkpoint: {e}")
                translated_subtitles = None
        
        # Translate from scratch if needed
        if translated_subtitles is None:
            try:
                if mode == 'naive':
                    translated_subtitles = self._translate_naive(subtitles, src_lang, target_lang, both, 
                                                                checkpoint_file=checkpoint_file if resume else None)
                else:
                    translated_subtitles = self._translate_split(subtitles, src_lang, target_lang, both, space,
                                                                checkpoint_file=checkpoint_file if resume else None)
            except (SubtitleError, TranslationError, RateLimitError) as e:
                logger.error(f"Translation failed: {e}")
                raise
        
        # Save translated subtitles
        try:
            self.subtitle_processor.save_file(translated_subtitles, output_file, encoding='UTF-8')
        except SubtitleError as e:
            logger.error(f"Failed to save subtitle file: {e}")
            raise
            
        # Update checkpoint to mark as complete
        if resume and os.path.exists(checkpoint_file):
            self._save_checkpoint(checkpoint_file, {
                'status': 'complete',
                'input_file': input_file,
                'output_file': output_file,
                'progress': 100
            })
        
        elapsed_time = time.time() - start_time
        logger.info(f"Translation completed in {elapsed_time:.2f} seconds")
    
    def _save_checkpoint(self, checkpoint_file: str, data: Dict[str, Any]) -> None:
        """Save translation progress to checkpoint file."""
        try:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved checkpoint to {checkpoint_file}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
    
    def _translate_naive(
        self,
        subtitles: List[Any],
        src_lang: str,
        target_lang: str,
        both: bool = True,
        checkpoint_file: Optional[str] = None
    ) -> List[Any]:
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
        content_list = [sub.content.replace('\n', '') for sub in subtitles]
        
        try:
            # Translate the content with progress reporting
            translated_text = None
            
            for retry_count in range(3):  # Allow a few retries for the entire batch
                try:
                    # Translate with progress tracking
                    translated_text = self._translate_with_progress(
                        content_list, src_lang, target_lang, 
                        checkpoint_file=checkpoint_file,
                        mode='naive'
                    )
                    break
                except RateLimitError as e:
                    if retry_count < 2:  # Only retry twice
                        backoff_time = 60 * (retry_count + 1)  # 60s, 120s
                        logger.warning(f"Rate limit detected. Backing off for {backoff_time}s before retry {retry_count+1}/3")
                        time.sleep(backoff_time)
                    else:
                        logger.error("Max retries reached after rate limiting")
                        raise
            
            if translated_text is None:
                raise TranslationError("Failed to translate content after retries")
                
            translated_list = translated_text.split('\n')
            
            # Handle potential mismatch in lists length
            if len(translated_list) != len(subtitles):
                logger.warning(f"Subtitle count mismatch: {len(subtitles)} vs {len(translated_list)}")
                # Try to fix by padding or truncating
                if len(translated_list) < len(subtitles):
                    translated_list.extend([''] * (len(subtitles) - len(translated_list)))
                else:
                    translated_list = translated_list[:len(subtitles)]
            
            # Apply translations to subtitle objects
            result = self.subtitle_processor.simple_translate_subtitles(subtitles, translated_list, both)
            
            # Save full completion to checkpoint
            if checkpoint_file:
                self._save_checkpoint(checkpoint_file, {
                    'status': 'translation_complete',
                    'progress': 100,
                    'mode': 'naive'
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Failed in naive translation mode: {e}")
            raise
    
    def _translate_with_progress(
        self, 
        text_list: List[str], 
        src_lang: str, 
        target_lang: str, 
        checkpoint_file: Optional[str] = None,
        mode: str = 'split'
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
                logger.info(f"Translation progress: {progress:.1f}% ({current}/{total})")
                last_progress_report = now
                
                # Update checkpoint with partial progress
                if checkpoint_file:
                    self._save_checkpoint(checkpoint_file, {
                        'status': 'translating',
                        'progress': progress,
                        'current_index': current,
                        'total_items': total,
                        'mode': mode,
                        'partial_translation': translated_so_far
                    })
        
        # Use the translator with progress tracking
        try:
            return self.translator.translate_lines(text_list, src_lang, target_lang, progress_callback)
        except Exception as e:
            logger.error(f"Translation with progress tracking failed: {e}")
            raise
    
    def _translate_split(
        self,
        subtitles: List[Any],
        src_lang: str,
        target_lang: str,
        both: bool = True,
        space: bool = False,
        checkpoint_file: Optional[str] = None
    ) -> List[Any]:
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
        
        logger.info(f"Split into {len(sen_list)} sentences")
        
        try:
            # Translate the sentences with progress reporting
            translated_sen = None
            
            for retry_count in range(3):  # Allow a few retries for the entire batch
                try:
                    # Translate with progress tracking
                    translated_sen = self._translate_with_progress(
                        sen_list, src_lang, target_lang, 
                        checkpoint_file=checkpoint_file,
                        mode='split'
                    )
                    break
                except RateLimitError as e:
                    if retry_count < 2:  # Only retry twice
                        backoff_time = 60 * (retry_count + 1)  # 60s, 120s
                        logger.warning(f"Rate limit detected. Backing off for {backoff_time}s before retry {retry_count+1}/3")
                        time.sleep(backoff_time)
                    else:
                        logger.error("Max retries reached after rate limiting")
                        raise
            
            if translated_sen is None:
                raise TranslationError("Failed to translate sentences after retries")
                
            translated_sen_list = translated_sen.split('\n')
            
            # Handle potential mismatch in lengths
            if len(translated_sen_list) != len(sen_list):
                logger.warning(
                    f"Sentence count mismatch after translation: {len(sen_list)} vs {len(translated_sen_list)}"
                )
                # Try to fix by padding or truncating
                if len(translated_sen_list) < len(sen_list):
                    translated_sen_list.extend([''] * (len(sen_list) - len(translated_sen_list)))
                else:
                    translated_sen_list = translated_sen_list[:len(sen_list)]
            
            # Compute mapping and convert sentences to dialogues
            mass_list = self.subtitle_processor.compute_mass_list(dialog_idx, sen_idx)
            
            # Special handling for Chinese
            cn = target_lang == 'zh-CN' or target_lang == 'zh-TW'
            dialog_list = self.subtitle_processor.sen_list2dialog_list(
                translated_sen_list, mass_list, space, cn
            )
            
            # Apply translations to subtitle objects
            result = self.subtitle_processor.advanced_translate_subtitles(subtitles, dialog_list, both)
            
            # Save full completion to checkpoint
            if checkpoint_file:
                self._save_checkpoint(checkpoint_file, {
                    'status': 'translation_complete',
                    'progress': 100,
                    'mode': 'split'
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Failed in split translation mode: {e}")
            raise
    
    def batch_translate_directory(
        self,
        input_dir: str,
        output_dir: str,
        src_lang: str,
        target_lang: str,
        file_pattern: str = "*.srt",
        encoding: str = 'UTF-8',
        mode: str = 'split',
        both: bool = True,
        space: bool = False,
        resume: bool = True
    ) -> Dict[str, Dict[str, Any]]:
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
        logger.info(f"Found {len(input_files)} subtitle files to translate")
        
        # Check for batch state file
        batch_state_file = os.path.join(output_dir, f"batch_state_{src_lang}_{target_lang}.json")
        batch_state = {}
        
        if resume and os.path.exists(batch_state_file):
            try:
                with open(batch_state_file, 'r', encoding='utf-8') as f:
                    batch_state = json.load(f)
                logger.info(f"Loaded batch state with {len(batch_state)} files")
            except Exception as e:
                logger.warning(f"Failed to load batch state: {e}")
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
            if resume and input_path in batch_state and batch_state[input_path].get('status') == 'success':
                logger.info(f"Skipping {input_path} (already completed according to batch state)")
                results[input_path] = batch_state[input_path]
                continue
            
            try:
                self.translate_file(
                    input_path, 
                    output_path, 
                    src_lang, 
                    target_lang, 
                    encoding, 
                    mode, 
                    both, 
                    space,
                    resume
                )
                results[input_path] = {"status": "success", "output": output_path}
                logger.info(f"Successfully translated {input_path} to {output_path}")
                
                # Update batch state
                if resume:
                    batch_state[input_path] = results[input_path]
                    with open(batch_state_file, 'w', encoding='utf-8') as f:
                        json.dump(batch_state, f, ensure_ascii=False, indent=2)
                
            except RateLimitError as e:
                # Special handling for rate limiting - record the error but continue with next file after a pause
                results[input_path] = {"status": "rate_limited", "message": str(e), "output": output_path}
                logger.error(f"Rate limited when translating {input_path}: {e}")
                logger.info("Pausing for 2 minutes before continuing with next file")
                time.sleep(120)  # 2 minute pause before trying the next file
                
                # Update batch state
                if resume:
                    batch_state[input_path] = results[input_path]
                    with open(batch_state_file, 'w', encoding='utf-8') as f:
                        json.dump(batch_state, f, ensure_ascii=False, indent=2)
                
            except Exception as e:
                results[input_path] = {"status": "error", "message": str(e)}
                logger.error(f"Failed to translate {input_path}: {e}")
                
                # Update batch state
                if resume:
                    batch_state[input_path] = results[input_path]
                    with open(batch_state_file, 'w', encoding='utf-8') as f:
                        json.dump(batch_state, f, ensure_ascii=False, indent=2)
        
        # Log summary
        success_count = sum(1 for result in results.values() if result["status"] == "success")
        rate_limited_count = sum(1 for result in results.values() if result["status"] == "rate_limited")
        logger.info(
            f"Translation complete: {success_count}/{len(input_files)} files successful, "
            f"{rate_limited_count} rate limited"
        )
        
        return results


def translate_and_compose(
    input_file: str,
    output_file: str,
    src_lang: str,
    target_lang: str,
    encoding: str = 'UTF-8',
    mode: str = 'split',
    both: bool = True,
    space: bool = False,
    api_key: Optional[str] = None,
    resume: bool = True
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
        input_file, output_file, src_lang, target_lang, encoding, mode, both, space, resume
    ) 