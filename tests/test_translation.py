"""
Tests for the translation module.
"""

import sys
import unittest
import urllib.error
from email.message import EmailMessage
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import requests

if TYPE_CHECKING:
    from typing import Any
else:
    from typing import Any  # noqa: F401

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import must happen after sys.path modification  # pylint: disable=wrong-import-position
from src.subtranslate.core.translation import (
    GoogleTranslator,
    RateLimitError,
    TkGenerator,
    TranslationError,
    Translator,
    get_translator,
)


class TestTkGenerator(unittest.TestCase):
    """Tests for the TkGenerator class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.tk_gen = TkGenerator()

    def test_initialization(self) -> None:
        """Test TkGenerator initialization."""
        self.assertIsNotNone(self.tk_gen.ctx)

    def test_get_tk(self) -> None:
        """Test get_tk method."""
        text = "Hello world"
        tk = self.tk_gen.get_tk(text)

        self.assertIsInstance(tk, str)
        self.assertIn(".", tk)  # TK format is typically "number.number"

    def test_get_tk_empty_string(self) -> None:
        """Test get_tk with empty string."""
        tk = self.tk_gen.get_tk("")
        self.assertIsInstance(tk, str)

    def test_get_tk_special_chars(self) -> None:
        """Test get_tk with special characters."""
        text = "Hello 世界! ñáéíóú"
        tk = self.tk_gen.get_tk(text)

        self.assertIsInstance(tk, str)
        self.assertIn(".", tk)

    @patch("src.subtranslate.core.translation.execjs.compile")
    def test_initialization_error(self, mock_compile: Mock) -> None:
        """Test TkGenerator initialization error."""
        mock_compile.side_effect = Exception("JS error")

        with self.assertRaises(TranslationError):
            TkGenerator()

    def test_get_tk_error(self) -> None:
        """Test get_tk error handling."""
        # Patch the ctx.call method on the instance
        with patch.object(
            self.tk_gen.ctx, "call", side_effect=Exception("JS call error")
        ):
            with self.assertRaises(TranslationError):
                self.tk_gen.get_tk("test")


class TestGoogleTranslator(unittest.TestCase):
    """Tests for the GoogleTranslator class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.translator = GoogleTranslator()

    def test_initialization_no_api_key(self) -> None:
        """Test initialization without API key."""
        translator = GoogleTranslator()

        self.assertIsNone(translator.api_key)
        self.assertIn("User-Agent", translator.headers)
        self.assertIsNotNone(translator.tk_gen)
        self.assertEqual(translator.max_limited, 3500)

    def test_initialization_with_api_key(self) -> None:
        """Test initialization with API key."""
        translator = GoogleTranslator(api_key="test_key")

        self.assertEqual(translator.api_key, "test_key")

    def test_rotate_user_agent(self) -> None:
        """Test user agent rotation."""
        _original_ua = self.translator.headers["User-Agent"]

        self.translator._rotate_user_agent()

        # Should still be one of the valid user agents
        self.assertIn(
            self.translator.headers["User-Agent"], self.translator.user_agents
        )

    def test_calculate_backoff(self) -> None:
        """Test backoff calculation."""
        backoff_0 = self.translator._calculate_backoff(0)
        backoff_1 = self.translator._calculate_backoff(1)
        backoff_2 = self.translator._calculate_backoff(2)

        self.assertGreaterEqual(backoff_0, 0.1)
        self.assertGreater(backoff_1, backoff_0 * 0.5)  # Account for jitter
        self.assertGreater(backoff_2, backoff_1 * 0.5)

        # Test max backoff
        backoff_large = self.translator._calculate_backoff(10)
        self.assertLessEqual(
            backoff_large, self.translator.max_backoff * 1.1
        )  # Account for jitter

    @patch("urllib.request.urlopen")
    def test_post_success(self, mock_urlopen: Mock) -> None:
        """Test successful POST request."""
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.read.return_value = b'{"result": "success"}'
        mock_urlopen.return_value = mock_response

        result = getattr(self.translator, "_GoogleTranslator__post")(
            "http://test.com", "test text"
        )

        self.assertEqual(result, '{"result": "success"}')

    @patch("urllib.request.urlopen")
    def test_post_rate_limit_retry(self, mock_urlopen: Mock) -> None:
        """Test POST request with rate limit retry."""
        # First call raises 429, second succeeds
        mock_response = MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.read.return_value = b'{"result": "success"}'

        # Set up side_effect with proper context managers
        def side_effect_func(*_args: object, **_kwargs: object) -> MagicMock:
            if not hasattr(side_effect_func, "call_count"):
                side_effect_func.call_count = 0  # type: ignore[attr-defined]
            side_effect_func.call_count += 1  # type: ignore[attr-defined]

            if side_effect_func.call_count == 1:  # type: ignore[attr-defined]
                headers = EmailMessage()
                raise urllib.error.HTTPError(
                    "http://test.com", 429, "Too Many Requests", headers, None
                )
            return mock_response

        mock_urlopen.side_effect = side_effect_func

        with patch("time.sleep") as mock_sleep:
            result = getattr(self.translator, "_GoogleTranslator__post")(
                "http://test.com", "test text"
            )

        self.assertEqual(result, '{"result": "success"}')
        mock_sleep.assert_called_once()  # Should have slept for backoff

    @patch("urllib.request.urlopen")
    def test_post_max_retries_exceeded(self, mock_urlopen: Mock) -> None:
        """Test POST request exceeding max retries."""
        headers = EmailMessage()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://test.com", 429, "Too Many Requests", headers, None
        )

        with patch("time.sleep"):
            with self.assertRaises(RateLimitError):
                getattr(self.translator, "_GoogleTranslator__post")(
                    "http://test.com", "test text"
                )

    @patch("urllib.request.urlopen")
    def test_post_network_error(self, mock_urlopen: Mock) -> None:
        """Test POST request with network error."""
        mock_urlopen.side_effect = urllib.error.URLError("Network error")

        with patch("time.sleep"):
            with self.assertRaises(TranslationError):
                getattr(self.translator, "_GoogleTranslator__post")(
                    "http://test.com", "test text"
                )

    @patch("urllib.request.urlopen")
    def test_post_http_error(self, mock_urlopen: Mock) -> None:
        """Test POST request with HTTP error (not rate limit)."""
        headers = EmailMessage()
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://test.com", 404, "Not Found", headers, None
        )

        with self.assertRaises(TranslationError):
            getattr(self.translator, "_GoogleTranslator__post")(
                "http://test.com", "test text"
            )

    @patch("requests.post")
    def test_translate_with_api_success(self, mock_post: Mock) -> None:
        """Test translation with API key success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"translations": [{"translatedText": "Hola mundo"}]}
        }
        mock_post.return_value = mock_response

        translator = GoogleTranslator(api_key="test_key")
        result = getattr(translator, "_GoogleTranslator__translate_with_api")(
            "Hello world", "en", "es"
        )

        self.assertEqual(result, "Hola mundo")

    @patch("requests.post")
    def test_translate_with_api_rate_limit(self, mock_post: Mock) -> None:
        """Test translation with API key rate limit."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response

        translator = GoogleTranslator(api_key="test_key")

        with patch("time.sleep"):
            with self.assertRaises(TranslationError) as context_manager:
                getattr(translator, "_GoogleTranslator__translate_with_api")(
                    "Hello world", "en", "es"
                )
            # Should contain rate limit information in the error message
            self.assertIn("rate limited", str(context_manager.exception).lower())

    @patch("requests.post")
    def test_translate_with_api_server_error(self, mock_post: Mock) -> None:
        """Test translation with API server error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        translator = GoogleTranslator(api_key="test_key")

        with patch("time.sleep"):
            with self.assertRaises(TranslationError):
                getattr(translator, "_GoogleTranslator__translate_with_api")(
                    "Hello world", "en", "es"
                )

    @patch("requests.post")
    def test_translate_with_api_network_error(self, mock_post: Mock) -> None:
        """Test translation with API network error."""
        mock_post.side_effect = requests.RequestException("Network error")

        translator = GoogleTranslator(api_key="test_key")

        with patch("time.sleep"):
            with self.assertRaises(TranslationError):
                getattr(translator, "_GoogleTranslator__translate_with_api")(
                    "Hello world", "en", "es"
                )

    def test_translate_without_api_success(self) -> None:
        """Test translation without API key success."""
        with patch.object(self.translator, "_GoogleTranslator__post") as mock_post:
            mock_post.return_value = '[["Hola mundo",null,null,null,null,null,null,[]]]'

            result = getattr(
                self.translator, "_GoogleTranslator__translate_without_api"
            )("Hello world", "en", "es")

        self.assertEqual(result, '[["Hola mundo",null,null,null,null,null,null,[]]]')

    def test_translate_without_api_all_domains_fail(self) -> None:
        """Test translation without API when all domains fail."""
        with patch.object(self.translator, "_GoogleTranslator__post") as mock_post:
            mock_post.side_effect = TranslationError("Failed")

            with self.assertRaises(TranslationError):
                getattr(self.translator, "_GoogleTranslator__translate_without_api")(
                    "Hello world", "en", "es"
                )

    def test_translate_raw(self) -> None:
        """Test translate_raw method."""
        with patch.object(
            self.translator, "_GoogleTranslator__translate"
        ) as mock_translate:
            mock_translate.return_value = "raw response"

            result = self.translator.translate_raw("Hello", "en", "es")

        self.assertEqual(result, "raw response")

    def test_translate_empty_text(self) -> None:
        """Test translate with empty text."""
        result = self.translator.translate("", "en", "es")
        self.assertEqual(result, "")

    def test_translate_whitespace_only(self) -> None:
        """Test translate with whitespace-only text."""
        result = self.translator.translate("   ", "en", "es")
        self.assertEqual(result, "")

    def test_translate_with_api_key(self) -> None:
        """Test translate method with API key."""
        translator = GoogleTranslator(api_key="test_key")

        with patch.object(
            translator, "_GoogleTranslator__translate_with_api"
        ) as mock_api_translate:
            mock_api_translate.return_value = "Hola mundo"

            result = translator.translate("Hello world", "en", "es")

        self.assertEqual(result, "Hola mundo")

    def test_translate_without_api_key(self) -> None:
        """Test translate method without API key."""
        with patch.object(
            self.translator, "_GoogleTranslator__translate_without_api"
        ) as mock_translate:
            # The correct format: outer array, then array of translation pairs, then metadata
            mock_translate.return_value = (
                '[[["Hola mundo","Hello world"],["additional","stuff"]], "metadata"]'
            )

            result = self.translator.translate("Hello world", "en", "es")

        self.assertEqual(result, "Hola mundo")

    def test_translate_json_decode_error(self) -> None:
        """Test translate with JSON decode error."""
        with patch.object(
            self.translator, "_GoogleTranslator__translate_without_api"
        ) as mock_translate:
            mock_translate.return_value = "invalid json"

            with self.assertRaises(TranslationError):
                self.translator.translate("Hello world", "en", "es")

    def test_translate_index_error(self) -> None:
        """Test translate with index/key error."""
        with patch.object(
            self.translator, "_GoogleTranslator__translate_without_api"
        ) as mock_translate:
            mock_translate.return_value = "[]"  # Empty array causes IndexError

            with self.assertRaises(TranslationError):
                self.translator.translate("Hello world", "en", "es")

    def test_translate_lines_empty_list(self) -> None:
        """Test translate_lines with empty list."""
        result = self.translator.translate_lines([], "en", "es")
        self.assertEqual(result, "")

    def test_translate_lines_success(self) -> None:
        """Test translate_lines success."""
        text_list = ["Hello", "World", "Test"]

        with patch.object(self.translator, "translate") as mock_translate:
            # translate_lines joins the texts with newlines and translates as one batch
            mock_translate.return_value = "Hola\nMundo\nPrueba"

            result = self.translator.translate_lines(text_list, "en", "es")

        self.assertIn("Hola", result)
        self.assertIn("Mundo", result)
        self.assertIn("Prueba", result)

    def test_translate_lines_with_progress_callback(self) -> None:
        """Test translate_lines with progress callback."""
        text_list = ["Hello", "World"]
        progress_calls = []

        def progress_callback(current: int, total: int, translated: str) -> None:
            progress_calls.append((current, total, translated))

        with patch.object(self.translator, "translate") as mock_translate:
            mock_translate.return_value = "Translated"

            self.translator.translate_lines(text_list, "en", "es", progress_callback)

        # Progress callback should be called
        self.assertTrue(len(progress_calls) > 0)

    def test_translate_lines_batching(self) -> None:
        """Test translate_lines with batching for large content."""
        # Create content that exceeds max_limited
        large_text_list = ["A" * 2000, "B" * 2000]  # Total > 3500 chars

        with patch.object(self.translator, "translate") as mock_translate:
            mock_translate.return_value = "Translated"

            _result = self.translator.translate_lines(large_text_list, "en", "es")

        # Should call translate multiple times for batching
        self.assertGreater(mock_translate.call_count, 1)

    def test_translate_lines_rate_limit_retry(self) -> None:
        """Test translate_lines with rate limit retry."""
        text_list = ["Hello"]

        with patch.object(self.translator, "translate") as mock_translate, patch(
            "time.sleep"
        ) as mock_sleep:

            # First call raises rate limit, second succeeds
            mock_translate.side_effect = [RateLimitError("Rate limited"), "Hola"]

            result = self.translator.translate_lines(text_list, "en", "es")

        mock_sleep.assert_called_once_with(30)  # Extended sleep for rate limit
        self.assertIn("Hola", result)

    def test_translate_lines_translation_error(self) -> None:
        """Test translate_lines with translation error."""
        text_list = ["Hello"]

        with patch.object(self.translator, "translate") as mock_translate:
            mock_translate.side_effect = TranslationError("Translation failed")

            with self.assertRaises(TranslationError):
                self.translator.translate_lines(text_list, "en", "es")


class TestGetTranslator(unittest.TestCase):
    """Tests for the get_translator factory function."""

    def test_get_google_translator(self) -> None:
        """Test getting Google translator."""
        translator = get_translator("google")

        self.assertIsInstance(translator, GoogleTranslator)
        self.assertIsNone(translator.api_key)  # type: ignore[attr-defined]

    def test_get_google_translator_with_api_key(self) -> None:
        """Test getting Google translator with API key."""
        translator = get_translator("google", "test_key")

        self.assertIsInstance(translator, GoogleTranslator)
        self.assertEqual(translator.api_key, "test_key")  # type: ignore[attr-defined]

    def test_get_google_translator_case_insensitive(self) -> None:
        """Test getting Google translator case insensitive."""
        translator = get_translator("GOOGLE")

        self.assertIsInstance(translator, GoogleTranslator)

    def test_get_unsupported_translator(self) -> None:
        """Test getting unsupported translator."""
        with self.assertRaises(ValueError):
            get_translator("unsupported_service")


class TestTranslatorInterface(unittest.TestCase):
    """Tests for the Translator abstract base class."""

    def test_translator_is_abstract(self) -> None:
        """Test that Translator cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            Translator()  # type: ignore[abstract]  # pylint: disable=abstract-class-instantiated

    def test_translator_interface_methods(self) -> None:
        """Test that Translator has required abstract methods."""
        # Check that the abstract methods exist
        self.assertTrue(hasattr(Translator, "translate"))
        self.assertTrue(hasattr(Translator, "translate_lines"))

        # Check they are marked as abstract
        self.assertTrue(getattr(Translator.translate, "__isabstractmethod__", False))
        self.assertTrue(
            getattr(Translator.translate_lines, "__isabstractmethod__", False)
        )


if __name__ == "__main__":
    unittest.main()
