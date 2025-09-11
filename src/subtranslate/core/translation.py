"""
Translation module for subtitle translation services.
Supports Google Translate and other translation services.
"""

import json
import logging
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import execjs
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """Exception raised for translation errors."""

    pass


class RateLimitError(TranslationError):
    """Exception raised specifically for rate limiting errors."""

    pass


class Translator(ABC):
    """Abstract base class for translation services."""

    @abstractmethod
    def translate(self, text: str, src_lang: str, target_lang: str) -> str:
        """Translate a text from source language to target language."""
        pass

    @abstractmethod
    def translate_lines(
        self, text_list: List[str], src_lang: str, target_lang: str, progress_callback=None
    ) -> str:
        """Translate a list of text lines."""
        pass


class GoogleTranslator(Translator):
    """Google Translate implementation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
        }
        self.tk_gen = TkGenerator()
        self.pattern = re.compile(r'\["(.*?)(?:\\n)')
        self.max_limited = 3500

        # Retry configuration
        self.max_retries = 5  # Maximum number of retry attempts
        self.initial_backoff = 2  # Initial backoff time in seconds
        self.max_backoff = 60  # Maximum backoff time in seconds
        self.jitter = 0.1  # Random jitter factor for backoff

        # Alternative user agents to rotate
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:94.0) Gecko/20100101 Firefox/94.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36",
        ]

    def _rotate_user_agent(self) -> None:
        """Rotate the user agent to avoid detection of automated requests."""
        self.headers["User-Agent"] = random.choice(self.user_agents)

    def _calculate_backoff(self, retry_count: int) -> float:
        """
        Calculate exponential backoff time with jitter.

        Args:
            retry_count: Current retry attempt number

        Returns:
            Backoff time in seconds
        """
        # Calculate exponential backoff: initial_backoff * 2^retry_count
        backoff = min(self.initial_backoff * (2**retry_count), self.max_backoff)

        # Add random jitter to avoid thundering herd problem
        jitter_amount = backoff * self.jitter
        backoff = backoff + random.uniform(-jitter_amount, jitter_amount)

        return max(backoff, 0.1)  # Ensure minimum delay of 0.1 seconds

    def __post(self, url: str, text: str) -> str:
        """Post a request to the translation service with retry mechanism."""
        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                # Rotate user agent before request
                if retry_count > 0:
                    self._rotate_user_agent()

                post_data = {"q": text}
                data = urllib.parse.urlencode(post_data).encode(encoding="utf-8")
                request = urllib.request.Request(url=url, data=data, headers=self.headers)

                response = urllib.request.urlopen(request, timeout=10)
                return response.read().decode("utf-8")

            except urllib.error.HTTPError as e:
                last_error = e
                # Check if this is a rate limit error (HTTP 429) or other server error (5xx)
                if e.code == 429 or (e.code >= 500 and e.code < 600):
                    retry_count += 1
                    if retry_count <= self.max_retries:
                        backoff_time = self._calculate_backoff(retry_count)
                        logger.warning(
                            f"Rate limit or server error detected (HTTP {e.code}). "
                            f"Retry {retry_count}/{self.max_retries} after {backoff_time:.2f}s backoff."
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        logger.error(f"Max retries reached after rate limit (HTTP {e.code})")
                        raise RateLimitError(
                            f"Translation service rate limited (HTTP {e.code}). Try again later."
                        )
                else:
                    # For other HTTP errors, fail immediately
                    logger.error(f"HTTP Error: {e}")
                    raise TranslationError(f"Translation service returned HTTP error: {e}")

            except urllib.error.URLError as e:
                last_error = e
                # Network errors could be temporary, retry with backoff
                retry_count += 1
                if retry_count <= self.max_retries:
                    backoff_time = self._calculate_backoff(retry_count)
                    logger.warning(
                        f"Network error: {e}. "
                        f"Retry {retry_count}/{self.max_retries} after {backoff_time:.2f}s backoff."
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"Max retries reached after network error: {e}")
                    raise TranslationError(
                        f"Failed to connect to translation service after {self.max_retries} attempts: {e}"
                    )

            except Exception as e:
                last_error = e
                # For other unexpected errors, retry with some backoff
                retry_count += 1
                if retry_count <= self.max_retries:
                    backoff_time = self._calculate_backoff(retry_count)
                    logger.warning(
                        f"Unexpected error: {e}. "
                        f"Retry {retry_count}/{self.max_retries} after {backoff_time:.2f}s backoff."
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"Max retries reached after unexpected error: {e}")
                    raise TranslationError(f"Unexpected translation error: {e}")

        # If we reach this point, all retries have failed
        if last_error:
            raise TranslationError(f"All translation attempts failed: {last_error}")
        else:
            raise TranslationError("All translation attempts failed for unknown reasons")

    def __translate(self, text: str, src_lang: str, target_lang: str) -> str:
        """Internal translation method."""
        if self.api_key:
            return self.__translate_with_api(text, src_lang, target_lang)
        else:
            return self.__translate_without_api(text, src_lang, target_lang)

    def __translate_with_api(self, text: str, src_lang: str, target_lang: str) -> str:
        """Translate using the official Google Cloud Translation API."""
        retry_count = 0
        last_error = None

        while retry_count <= self.max_retries:
            try:
                url = f"https://translation.googleapis.com/language/translate/v2?key={self.api_key}"
                payload = {"q": text, "source": src_lang, "target": target_lang, "format": "text"}
                response = requests.post(url, data=payload)

                if response.status_code == 429:  # Rate limit error
                    retry_count += 1
                    if retry_count <= self.max_retries:
                        backoff_time = self._calculate_backoff(retry_count)
                        logger.warning(
                            f"API rate limit detected. "
                            f"Retry {retry_count}/{self.max_retries} after {backoff_time:.2f}s backoff."
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        logger.error("Max retries reached after API rate limit")
                        raise RateLimitError("Translation API rate limited. Try again later.")
                elif response.status_code >= 500:  # Server error
                    retry_count += 1
                    if retry_count <= self.max_retries:
                        backoff_time = self._calculate_backoff(retry_count)
                        logger.warning(
                            f"API server error ({response.status_code}). "
                            f"Retry {retry_count}/{self.max_retries} after {backoff_time:.2f}s backoff."
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        logger.error(
                            f"Max retries reached after API server error: {response.status_code}"
                        )
                        raise TranslationError(f"Translation API server error: {response.text}")
                elif response.status_code != 200:  # Other errors
                    logger.error(f"API Error: {response.text}")
                    raise TranslationError(f"Translation API error: {response.text}")

                result = response.json()
                return result["data"]["translations"][0]["translatedText"]

            except requests.RequestException as e:
                last_error = e
                # Network errors could be temporary, retry with backoff
                retry_count += 1
                if retry_count <= self.max_retries:
                    backoff_time = self._calculate_backoff(retry_count)
                    logger.warning(
                        f"API request error: {e}. "
                        f"Retry {retry_count}/{self.max_retries} after {backoff_time:.2f}s backoff."
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"Max retries reached after API request error: {e}")
                    raise TranslationError(
                        f"Failed to connect to Google Translation API after {self.max_retries} attempts: {e}"
                    )

            except KeyError as e:
                last_error = e
                # Response parsing errors, could be due to API changes
                retry_count += 1
                if retry_count <= self.max_retries:
                    backoff_time = self._calculate_backoff(retry_count)
                    logger.warning(
                        f"API response parsing error: {e}. "
                        f"Retry {retry_count}/{self.max_retries} after {backoff_time:.2f}s backoff."
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"Max retries reached after API response parsing error: {e}")
                    raise TranslationError(f"Failed to parse API response: {e}")

            except Exception as e:
                last_error = e
                # Other unexpected errors
                retry_count += 1
                if retry_count <= self.max_retries:
                    backoff_time = self._calculate_backoff(retry_count)
                    logger.warning(
                        f"Unexpected API error: {e}. "
                        f"Retry {retry_count}/{self.max_retries} after {backoff_time:.2f}s backoff."
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"Max retries reached after unexpected API error: {e}")
                    raise TranslationError(f"Unexpected translation API error: {e}")

        # If we reach this point, all retries have failed
        if last_error:
            raise TranslationError(f"All API translation attempts failed: {last_error}")
        else:
            raise TranslationError("All API translation attempts failed for unknown reasons")

    def __translate_without_api(self, text: str, src_lang: str, target_lang: str) -> str:
        """Translate using the free Google Translate service."""
        tk = self.tk_gen.get_tk(text)
        # Try different Google Translate domains if one fails
        domains = ["translate.google.com", "translate.google.cn"]

        # Try each domain
        last_error = None
        for domain in domains:
            url = (
                f"http://{domain}/translate_a/single?client=t"
                f"&sl={src_lang}&tl={target_lang}&dt=at&dt=bd&dt=ex&dt=ld&dt=md&dt=qca"
                f"&dt=rw&dt=rm&dt=ss&dt=t&ie=UTF-8&oe=UTF-8&clearbtn=1&otf=1&pc=1"
                f"&srcrom=0&ssel=0&tsel=0&kc=1&tk={tk}"
            )

            try:
                result = self.__post(url, text)
                return result
            except TranslationError as e:
                last_error = e
                logger.warning(f"Translation failed with domain {domain}: {e}. Trying next domain.")
                continue

        # If all domains failed, raise the last error
        if last_error:
            raise last_error
        else:
            raise TranslationError("All Google Translate domains failed for unknown reasons")

    def translate_raw(self, text: str, src_lang: str, target_lang: str) -> str:
        """
        Return raw response from translation service.

        Args:
            text: Origin text
            src_lang: Source language code
            target_lang: Target language code

        Returns:
            Raw response string
        """
        return self.__translate(text, src_lang, target_lang)

    def translate(self, text: str, src_lang: str, target_lang: str) -> str:
        """
        Translate text from source language to target language.

        Args:
            text: Origin text
            src_lang: Source language code (ISO-639-1)
            target_lang: Target language code (ISO-639-1)

        Returns:
            Translated text

        Raises:
            TranslationError: If translation fails
            RateLimitError: If translation fails due to rate limiting
        """
        if not text.strip():
            return ""

        try:
            result = self.__translate(text, src_lang, target_lang)

            if self.api_key:
                return result

            obj_result = json.loads(result)
            list_sentence = [x[0] for x in obj_result[0][:-1]]
            return "".join(list_sentence)
        except json.JSONDecodeError:
            logger.error("Failed to decode translation response")
            raise TranslationError("Failed to decode translation response")
        except (IndexError, KeyError):
            logger.error("Failed to parse translation response")
            raise TranslationError("Failed to parse translation response")
        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise TranslationError(f"Translation error: {e}")

    def translate_lines(
        self, text_list: List[str], src_lang: str, target_lang: str, progress_callback=None
    ) -> str:
        """
        Translate a list of text lines with checkpoint support.

        Args:
            text_list: List of texts to translate
            src_lang: Source language code
            target_lang: Target language code
            progress_callback: Optional callback function(current, total, translated_so_far)

        Returns:
            Translated text with newlines

        Raises:
            TranslationError: If translation fails
            RateLimitError: If translation fails due to rate limiting
        """
        if not text_list:
            return ""

        translated = ""
        last_idx = 0
        total_length = 0

        # Track progress to allow resuming on failure
        progress = []

        try:
            for i in range(len(text_list)):
                total_length += len(text_list[i])
                if total_length > self.max_limited:
                    batch = "\n".join(text_list[last_idx:i])
                    if batch.strip():  # Only translate non-empty batches
                        # Track progress before translation attempt
                        checkpoint = (last_idx, i)

                        try:
                            batch_translation = self.translate(batch, src_lang, target_lang)
                            translated += batch_translation
                            translated += "\n"

                            # Record successful translation
                            progress.append((checkpoint, True))

                            # Call progress callback if provided
                            if progress_callback:
                                progress_callback(i, len(text_list), translated)

                        except RateLimitError:
                            # Special handling for rate limit errors - longer backoff
                            logger.warning(
                                "Rate limit detected during batch translation. Backing off for 30 seconds."
                            )
                            time.sleep(30)  # Extended sleep for rate limit

                            # Try again with the same batch
                            batch_translation = self.translate(batch, src_lang, target_lang)
                            translated += batch_translation
                            translated += "\n"

                            # Record successful retry
                            progress.append((checkpoint, True))

                            # Call progress callback if provided
                            if progress_callback:
                                progress_callback(i, len(text_list), translated)

                        except TranslationError as e:
                            # Record failed translation
                            progress.append((checkpoint, False))
                            raise e

                    # Adaptive delay based on recent translation history and batch size
                    delay = 1 + (len(batch) / 2000)  # Longer delays for larger batches
                    logger.info(
                        f"Pausing for {delay:.2f}s between translation batches to avoid rate limiting"
                    )
                    time.sleep(delay)

                    last_idx = i
                    total_length = 0

            # Translate the last batch
            last_batch = "\n".join(text_list[last_idx:])
            if last_batch.strip():  # Only translate non-empty batches
                # Track final batch
                final_checkpoint = (last_idx, len(text_list))

                try:
                    translated += self.translate(last_batch, src_lang, target_lang)
                    # Record successful final batch
                    progress.append((final_checkpoint, True))

                    # Final progress callback
                    if progress_callback:
                        progress_callback(len(text_list), len(text_list), translated)

                except RateLimitError:
                    # Special handling for rate limit errors
                    logger.warning(
                        "Rate limit detected during final batch translation. Backing off for 30 seconds."
                    )
                    time.sleep(30)

                    # Try again with the final batch
                    translated += self.translate(last_batch, src_lang, target_lang)
                    # Record successful retry of final batch
                    progress.append((final_checkpoint, True))

                    # Final progress callback
                    if progress_callback:
                        progress_callback(len(text_list), len(text_list), translated)

                except TranslationError as e:
                    # Record failed final batch
                    progress.append((final_checkpoint, False))
                    raise e

            return translated

        except Exception as e:
            # Find the last successful batch from progress
            successful_batches = [idx for idx, success in progress if success]
            if successful_batches:
                last_successful = max(successful_batches)
                fail_point = last_successful[1]  # The end index of the last successful batch
                logger.error(
                    f"Translation failed at position {fail_point}/{len(text_list)} "
                    f"({(fail_point/len(text_list))*100:.1f}% complete): {e}"
                )
            else:
                logger.error(f"Translation failed before any batches were completed: {e}")

            logger.error(f"Failed to translate lines: {e}")
            raise TranslationError(f"Failed to translate lines: {e}")


class TkGenerator:
    """Generate TK parameter for Google Translate requests."""

    def __init__(self):
        try:
            self.ctx = execjs.compile(
                """
            function TL(a) {
            var k = "";
            var b = 406644;
            var b1 = 3293161072;
            var jd = ".";
            var $b = "+-a^+6";
            var Zb = "+-3^+b+-f";
            for (var e = [], f = 0, g = 0; g < a.length; g++) {
                var m = a.charCodeAt(g);
                128 > m ? e[f++] = m : (2048 > m ? e[f++] = m >> 6 | 192 : (55296 == (m & 64512) && g + 1 < a.length && 56320 == (a.charCodeAt(g + 1) & 64512) ? (m = 65536 + ((m & 1023) << 10) + (a.charCodeAt(++g) & 1023),
                e[f++] = m >> 18 | 240,
                e[f++] = m >> 12 & 63 | 128) : e[f++] = m >> 12 | 224,
                e[f++] = m >> 6 & 63 | 128),
                e[f++] = m & 63 | 128)
            }
            a = b;
            for (f = 0; f < e.length; f++) a += e[f],
            a = RL(a, $b);
            a = RL(a, Zb);
            a ^= b1 || 0;
            0 > a && (a = (a & 2147483647) + 2147483648);
            a %= 1E6;
            return a.toString() + jd + (a ^ b)
        };
        function RL(a, b) {
            var t = "a";
            var Yb = "+";
            for (var c = 0; c < b.length - 2; c += 3) {
                var d = b.charAt(c + 2),
                d = d >= t ? d.charCodeAt(0) - 87 : Number(d),
                d = b.charAt(c + 1) == Yb ? a >>> d: a << d;
                a = b.charAt(c) == Yb ? a + d & 4294967295 : a ^ d
            }
            return a
        }
        """
            )
        except Exception as e:
            logger.error(f"Failed to initialize TkGenerator: {e}")
            raise TranslationError(f"Failed to initialize JavaScript context for translation: {e}")

    def get_tk(self, text: str) -> str:
        """Generate the TK parameter for a given text."""
        try:
            return self.ctx.call("TL", text)
        except Exception as e:
            logger.error(f"Failed to generate TK: {e}")
            raise TranslationError(f"Failed to generate translation key: {e}")


def get_translator(service: str = "google", api_key: Optional[str] = None) -> Translator:
    """
    Factory function to get a translator instance.

    Args:
        service: Translation service to use ('google' is currently the only supported option)
        api_key: API key for the translation service (optional)

    Returns:
        Translator instance

    Raises:
        ValueError: If service is not supported
    """
    if service.lower() == "google":
        return GoogleTranslator(api_key)
    else:
        raise ValueError(f"Unsupported translation service: {service}")
