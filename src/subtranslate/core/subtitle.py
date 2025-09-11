"""
SRT subtitle utilities module for parsing, manipulating, and saving subtitle files.
"""

import logging
import os
import re
from datetime import timedelta
from typing import Dict, List, Protocol, Tuple, Union

import srt


class SubtitleLike(Protocol):
    """Protocol for subtitle objects with required attributes."""

    index: int
    start: timedelta
    end: timedelta
    content: str
    proprietary: str


# Type alias for better clarity
SubtitleList = List[SubtitleLike]

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Try importing jieba for Chinese segmentation, but don't fail if not available
try:
    import jieba

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning(
        "Jieba library not found. Chinese segmentation may not work correctly."
    )


class SubtitleError(Exception):
    """Exception raised for subtitle processing errors."""


class Splitter:
    """Sentence splitter for text processing."""

    def __init__(self) -> None:
        # Improved regex pattern for sentence splitting
        self.pattern = re.compile(
            r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<!\b[A-Za-z]\.)(?<=\.|\?|\!)\s"
        )

    def split(self, text: str) -> List[str]:
        """
        Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        if not text:
            return []

        # Use regex to split on sentence boundaries
        sentences = self.pattern.split(text)

        # Filter out empty strings
        return [s for s in sentences if s.strip()]


class SubtitleProcessor:
    """Process subtitle files for translation."""

    def __init__(self) -> None:
        self.splitter = Splitter()

    def parse_file(self, file_path: str, encoding: str = "UTF-8") -> SubtitleList:
        """
        Parse an SRT file into subtitle objects.

        Args:
            file_path: Path to the SRT file
            encoding: File encoding

        Returns:
            List of srt.Subtitle objects

        Raises:
            SubtitleError: If file can't be parsed
        """
        if not os.path.exists(file_path):
            raise SubtitleError(f"Subtitle file not found: {file_path}")

        try:
            with open(file_path, encoding=encoding) as srt_file:
                content = srt_file.read()
                subtitle_generator = srt.parse(content)
                return list(subtitle_generator)
        except UnicodeDecodeError as exc:
            logger.error(
                "Failed to decode file with encoding %s. Try another encoding.",
                encoding,
            )
            raise SubtitleError(
                f"Failed to decode subtitle file with encoding {encoding}. "
                "Try UTF-8-sig or another encoding."
            ) from exc
        except srt.SRTParseError as e:
            logger.error("Failed to parse SRT file: %s", e)
            raise SubtitleError(f"Failed to parse SRT file: {e}") from e
        except Exception as e:
            logger.error("Error reading subtitle file: %s", e)
            raise SubtitleError(f"Error reading subtitle file: {e}") from e

    def save_file(
        self, subtitles: SubtitleList, file_path: str, encoding: str = "UTF-8"
    ) -> None:
        """
        Save subtitles to an SRT file.

        Args:
            subtitles: List of subtitle objects
            file_path: Output file path
            encoding: File encoding

        Raises:
            SubtitleError: If file can't be saved
        """
        try:

            # Ensure subtitles are proper srt.Subtitle objects
            valid_subtitles = []
            for sub in subtitles:
                if not isinstance(sub, srt.Subtitle):
                    # Try to convert to srt.Subtitle if it's a dict or similar
                    try:
                        valid_sub = srt.Subtitle(
                            index=getattr(sub, "index", 0),
                            start=getattr(sub, "start", timedelta()),
                            end=getattr(sub, "end", timedelta()),
                            content=getattr(sub, "content", ""),
                        )
                        valid_subtitles.append(valid_sub)
                    except (AttributeError, TypeError, ValueError) as exc:
                        logger.warning("Failed to convert subtitle: %s", exc)
                else:
                    valid_subtitles.append(sub)

            with open(file_path, "w", encoding=encoding) as f:
                f.write(srt.compose(valid_subtitles))
            logger.info("Saved subtitles to %s", file_path)
        except Exception as e:
            logger.error("Failed to save subtitles: %s", e)
            raise SubtitleError(f"Failed to save subtitles: {e}") from e

    def triple_r(self, subtitle_list: SubtitleList) -> Tuple[str, List[int]]:
        """
        Remove line breaks, reconstruct plain text, and record dialogue indices.

        Args:
            subtitle_list: List of subtitle objects

        Returns:
            Tuple of (plain text, dialogue indices)
        """
        dialog_idx = []
        current_idx = 0
        plain_text = ""

        for sub in subtitle_list:
            # Normalize content by replacing line breaks with spaces
            content = sub.content.replace("\n", " ") + " "
            current_idx += len(content)
            dialog_idx.append(current_idx)
            plain_text += content

        # Remove trailing space
        return plain_text.rstrip(), dialog_idx

    def split_and_record(self, plain_text: str) -> Tuple[List[str], List[int]]:
        """
        Split plain text into sentences and record sentence indices.

        Args:
            plain_text: Plain text from subtitle content

        Returns:
            Tuple of (sentence list, sentence indices)
        """
        sen_list = self.splitter.split(plain_text)
        sen_idx = [0]
        current_idx = 0

        for sen in sen_list:
            sen_len = len(sen) + 1  # +1 for the space
            current_idx += sen_len
            sen_idx.append(current_idx)

        return sen_list, sen_idx

    def compute_mass_list(
        self, dialog_idx: List[int], sen_idx: List[int]
    ) -> List[List[Tuple[int, int]]]:
        """
        Compute relationships between sentences and dialogues.

        Args:
            dialog_idx: List of dialog end indices
            sen_idx: List of sentence end indices

        Returns:
            List of sentence-dialogue relationships
        """
        i = 0
        j = 1
        mass_list = []
        one_sentence: list[tuple[int, int]] = []

        while i < len(dialog_idx):
            if dialog_idx[i] > sen_idx[j]:
                mass_list.append(one_sentence)
                one_sentence = []
                j += 1
            else:
                one_sentence.append((i + 1, dialog_idx[i] - sen_idx[j - 1]))
                i += 1

        # Add the last sentence
        if one_sentence:
            mass_list.append(one_sentence)

        return mass_list

    def get_nearest_space(self, sentence: str, current_idx: int) -> int:
        """
        Find the nearest space to split at in a space-delimited language.

        Args:
            sentence: Text to split
            current_idx: Target position

        Returns:
            Index of nearest space
        """
        if not sentence:
            return 0

        left_idx = sentence[:current_idx].rfind(" ")
        right_idx = sentence[current_idx:].find(" ")

        # If no space found, return current position
        if left_idx == -1 and right_idx == -1:
            return current_idx

        # If no space on left, use right
        if left_idx == -1:
            return right_idx + current_idx + 1

        # If no space on right, use left
        if right_idx == -1:
            return left_idx + 1

        # Choose the nearest
        if current_idx - left_idx > right_idx:
            return right_idx + current_idx + 1

        return left_idx + 1

    def get_nearest_split_cn(
        self, sentence: str, current_idx: int, last_idx: int, scope: int = 6
    ) -> int:
        """
        Find the nearest word boundary in Chinese text using jieba.

        Args:
            sentence: Chinese text
            current_idx: Target position
            last_idx: Last split position
            scope: Scope to consider for segmentation

        Returns:
            Index for splitting
        """
        if not JIEBA_AVAILABLE:
            logger.warning("Jieba not available for Chinese segmentation")
            return current_idx

        if not sentence:
            return 0

        # Adjust boundaries
        last_idx = max(last_idx, current_idx - scope)
        next_idx = min(current_idx + scope, len(sentence))

        try:
            words = list(jieba.cut(sentence[last_idx:next_idx]))

            total_len = 0
            word_idx = 0
            target_idx = current_idx - last_idx

            for word in words:
                total_len += len(word)
                word_idx += 1
                if total_len >= target_idx:
                    break

            # If we found a word and it's a Chinese comma, include it
            if word_idx < len(words) and words[word_idx] == "\uff0c":
                total_len += len(words[word_idx])

            return total_len + last_idx
        except (AttributeError, RuntimeError) as e:
            logger.error("Error in Chinese segmentation: %s", e)
            return current_idx

    def sen_list2dialog_list(
        self,
        sen_list: List[str],
        mass_list: List[List[Tuple[int, int]]],
        space: bool = False,
        is_chinese: bool = False,
    ) -> List[str]:
        """
        Convert sentence list to dialogue list.

        Args:
            sen_list: List of sentences
            mass_list: Mapping of sentences to dialogues
            space: Whether target language uses spaces
            is_chinese: Whether target language is Chinese

        Returns:
            List of dialogues
        """
        if not sen_list or not mass_list:
            return []

        # Initialize with empty strings
        dialog_num = mass_list[-1][-1][0] if mass_list and mass_list[-1] else 0
        if dialog_num == 0:
            logger.warning("No dialogues found in mass_list")
            return []

        dialog_list = [""] * dialog_num

        for sen_idx, sentence in enumerate(sen_list):
            if sen_idx >= len(mass_list):
                logger.warning(
                    "Mass list index out of range: %d >= %d", sen_idx, len(mass_list)
                )
                break

            record = mass_list[sen_idx]

            if not record:
                logger.warning("Empty record for sentence %d", sen_idx)
                continue

            total_dialog_of_sentence = len(record)

            if total_dialog_of_sentence == 1:
                # Simple case: one sentence, one dialogue
                dialog_list[record[0][0] - 1] += sentence[0 : record[0][1]]
            else:
                # Complex case: one sentence spans multiple dialogues
                if not record:
                    logger.warning("Empty record for sentence %d", sen_idx)
                    continue

                origin_len = record[-1][1]
                translated_len = len(sentence)

                last_idx = 0
                for record_idx in range(len(record) - 1):
                    current_idx = int(
                        translated_len * record[record_idx][1] / origin_len
                    )

                    # Different splitting strategies based on language type
                    if space and not is_chinese:
                        # Space-delimited language: split at word boundaries
                        current_idx = self.get_nearest_space(sentence, current_idx)
                    elif is_chinese:
                        # Chinese: use jieba to split at word boundaries
                        current_idx = self.get_nearest_split_cn(
                            sentence, current_idx, last_idx
                        )

                    # Add segment to dialogue
                    if record[record_idx][0] - 1 < len(dialog_list):
                        dialog_list[record[record_idx][0] - 1] += sentence[
                            last_idx:current_idx
                        ]
                    last_idx = current_idx

                # Add last segment
                if record[-1][0] - 1 < len(dialog_list):
                    dialog_list[record[-1][0] - 1] += sentence[last_idx:]

        return dialog_list

    def simple_translate_subtitles(
        self, subtitles: SubtitleList, translated_texts: List[str], both: bool = True
    ) -> SubtitleList:
        """
        Apply translated texts to subtitles (simple mode).

        Args:
            subtitles: Original subtitle objects
            translated_texts: Translated texts for each subtitle
            both: Whether to keep original text

        Returns:
            Updated subtitle objects
        """
        if len(subtitles) != len(translated_texts):
            raise SubtitleError(
                f"Subtitle count mismatch: {len(subtitles)} vs {len(translated_texts)}"
            )

        result = []
        for i, sub in enumerate(subtitles):
            content = translated_texts[i]
            if both:
                content += "\n" + sub.content.replace("\n", " ")

            new_sub = srt.Subtitle(
                index=sub.index,
                start=sub.start,
                end=sub.end,
                content=content,
                proprietary=sub.proprietary,
            )
            result.append(new_sub)

        return result

    def advanced_translate_subtitles(
        self, subtitles: SubtitleList, translated_dialogs: List[str], both: bool = True
    ) -> SubtitleList:
        """
        Apply translated dialogues to subtitles (advanced mode).

        Args:
            subtitles: Original subtitle objects
            translated_dialogs: Translated dialogues
            both: Whether to keep original text

        Returns:
            Updated subtitle objects
        """
        if len(subtitles) != len(translated_dialogs):
            raise SubtitleError(
                f"Subtitle count mismatch: {len(subtitles)} vs {len(translated_dialogs)}"
            )

        result = []
        for i, sub in enumerate(subtitles):
            content = translated_dialogs[i]
            if both:
                content += "\n" + sub.content.replace("\n", " ")

            new_sub = srt.Subtitle(
                index=sub.index,
                start=sub.start,
                end=sub.end,
                content=content,
                proprietary=sub.proprietary,
            )
            result.append(new_sub)

        return result

    def to_serialized(
        self, subtitles: SubtitleList
    ) -> List[Dict[str, Union[str, timedelta, int, None]]]:
        """
        Convert subtitle objects to a serializable format for checkpointing.

        Args:
            subtitles: List of subtitle objects

        Returns:
            List of serialized subtitle dictionaries
        """
        serialized = []
        for sub in subtitles:
            serialized.append(
                {
                    "index": sub.index,
                    "start_time": sub.start,
                    "end_time": sub.end,
                    "content": sub.content,
                    "translated_content": getattr(sub, "translated_content", None),
                }
            )
        return serialized

    def from_serialized(
        self, serialized: List[Dict[str, Union[str, None]]]
    ) -> SubtitleList:
        """
        Reconstruct subtitle objects from serialized format.

        Args:
            serialized: List of serialized subtitle dictionaries

        Returns:
            List of subtitle objects
        """
        # srt module already imported at module level

        subtitles = []
        for data in serialized:
            sub = srt.Subtitle(
                index=data["index"],
                start=data["start_time"],
                end=data["end_time"],
                content=data["content"],
            )
            if data.get("translated_content") is not None:
                sub.translated_content = data["translated_content"]
            subtitles.append(sub)
        return subtitles
