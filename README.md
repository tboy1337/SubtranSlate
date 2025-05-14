# SubtranSlate

A powerful and flexible tool for translating subtitle files between languages. Currently supports SRT format.

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.3-blue)
![Python](https://img.shields.io/badge/python-3.6+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

</div>

## 📋 Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
  - [Command-Line Interface](#command-line-interface)
  - [Encoding Conversion](#encoding-conversion)
  - [Examples](#examples)
  - [Programmatic Usage](#programmatic-usage)
- [How it Works](#how-it-works)
- [Rate Limiting Protection](#rate-limiting-protection)
- [Supported Languages](#supported-languages)
- [Supported Encodings](#supported-encodings)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## ✨ Features

- **Accurate Translation**: Translate subtitle files between languages while preserving formatting and timing
- **Context-Aware**: Two translation modes to handle context appropriately:
  - **Split mode**: For context-aware translations of sentences spanning multiple subtitles
  - **Naive mode**: For direct translation of subtitle content without context
- **Batch Processing**: Process multiple subtitle files in one operation
- **Rate Limiting Protection**: Built-in exponential backoff and resume functionality
- **Flexible Options**:
  - Support for various text encodings (UTF-8, UTF-8-sig, TIS-620, etc.)
  - Optional Google Cloud Translation API integration
  - Display original and translated text together or only translations
- **Encoding Conversion**: Convert subtitle files between different character encodings
- **Cross-Platform**: Works on Windows, macOS, and Linux

## 🔧 Installation

### From PyPI (Recommended)

```bash
pip install subtranslate-py
```

> **Note:** While the PyPI package name is `subtranslate-py`, the package is still imported and used as `subtranslate` in your code.

### From Source

```bash
git clone https://github.com/tboy1337/SubtranSlate.git
cd SubtranSlate
pip install -e .
```

### Running Without Installation

If you prefer to run without installing:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py [options]
```

### Dependencies

- Python 3.6+
- Required packages:
  - `pyexecjs`: For JavaScript code interaction
  - `srt`: For SRT file parsing and manipulation
  - `requests`: For API communication
  - `jieba`: For Chinese segmentation (recommended for Chinese translations)

## 🚀 Quick Start

Translate a subtitle file from English to Spanish:

```bash
# If installed via pip
subtranslate input.srt output.srt -s en -t es

# If running from source
python run.py input.srt output.srt -s en -t es
```

## 📖 Usage Guide

### Command-Line Interface

The application provides two main commands:

1. `translate` - Translate subtitle files (default command)
2. `encode` - Convert subtitle files between different encodings

#### Translate Command

```bash
subtranslate translate [options] input_file output_file
```

Or if running from source:

```bash
python run.py translate [options] input_file output_file
```

#### Encode Command

```bash
subtranslate encode [options] input_file
```

Or if running from source:

```bash
python run.py encode [options] input_file
```

#### CLI Options for Translation

| Argument | Description |
|----------|-------------|
| `input` | Input subtitle file or directory containing subtitle files |
| `output` | Output subtitle file or directory for translated files |
| `--src-lang`, `-s` | Source language code (default: en) |
| `--target-lang`, `-t` | Target language code (default: zh-CN) |
| `--mode {naive,split}` | Translation mode (default: split) |
| `--both` | Include both original and translated text (default: True) |
| `--only-translation` | Include only translated text |
| `--space` | Target language uses spaces between words (default: False) |
| `--encoding` | Input file encoding (default: UTF-8) |
| `--batch` | Process input as directory containing multiple subtitle files |
| `--pattern` | File pattern for batch processing (default: *.srt) |
| `--api-key` | API key for translation service (optional) |
| `--service` | Translation service to use (default: google) |
| `--verbose`, `-v` | Enable verbose logging |
| `--no-resume` | Do not attempt to resume from previous translations |

#### CLI Options for Encoding Conversion

| Argument | Description |
|----------|-------------|
| `input` | Input subtitle file or directory containing subtitle files |
| `--output-dir`, `-o` | Output directory for converted files (default: same as input) |
| `--from-encoding`, `-f` | Source encoding (auto-detect if not specified) |
| `--to-encoding`, `-t` | Target encodings (comma-separated list) |
| `--all`, `-a` | Convert to all supported encodings |
| `--recommended`, `-r` | Use recommended encodings based on language |
| `--language`, `-l` | Language code for recommended encodings (default: en) |
| `--list-encodings` | List all supported encodings |
| `--batch` | Process input as directory containing multiple subtitle files |
| `--pattern` | File pattern for batch processing (default: *.srt) |
| `--verbose`, `-v` | Enable verbose logging |

### Encoding Conversion

SubtranSlate now includes a powerful encoding conversion system to handle subtitles in various character encodings, including TIS-620 for Thai subtitles and many other regional encodings.

#### Basic Encoding Conversion

Convert a subtitle file to TIS-620 encoding:

```bash
subtranslate encode sample.srt --to-encoding tis-620
```

#### Convert to Multiple Encodings

Convert a subtitle file to multiple encodings at once:

```bash
subtranslate encode sample.srt --to-encoding "utf-8,tis-620,cp874,iso8859-11"
```

#### Use Recommended Encodings for a Language

Convert using encodings recommended for Thai:

```bash
subtranslate encode sample.srt --recommended --language th
```

#### Convert All Files in a Directory

Convert all subtitle files in a directory to TIS-620:

```bash
subtranslate encode subtitles/ --batch --to-encoding tis-620
```

#### List All Supported Encodings

```bash
subtranslate encode --list-encodings
```

### Examples

#### Basic Translation (English to Chinese)

```bash
subtranslate sample.en.srt sample_en_cn_both.srt -s en -t zh-CN
```

#### Translation Only (No Original Text)

```bash
subtranslate sample.en.srt sample_cn_only.srt -s en -t zh-CN --only-translation
```

#### Batch Processing

```bash
subtranslate --batch input_directory output_directory -s en -t fr
```

#### Using Google Cloud Translation API

```bash
subtranslate sample.en.srt sample_translated.srt --api-key YOUR_API_KEY
```

#### Disable Resume Functionality

```bash
subtranslate sample.en.srt sample_translated.srt -s en -t fr --no-resume
```

### Programmatic Usage

Import the library in your Python code:

```python
from subtranslate.core.main import translate_and_compose

# Basic usage - English to Chinese with both languages in output
translate_and_compose(
    input_file='sample.en.srt', 
    output_file='sample_en_cn_both.srt', 
    src_lang='en', 
    target_lang='zh-CN'
)

# Chinese translation only (no original text)
translate_and_compose(
    input_file='sample.en.srt', 
    output_file='sample_cn_only.srt', 
    src_lang='en', 
    target_lang='zh-CN', 
    both=False
)

# For languages using spaces between words (like German)
translate_and_compose(
    input_file='sample.en.srt', 
    output_file='sample_en_de_both.srt', 
    src_lang='en', 
    target_lang='de', 
    space=True
)

# For languages not using spaces (like Japanese)
translate_and_compose(
    input_file='sample.en.srt', 
    output_file='sample_en_ja_both.srt', 
    src_lang='en', 
    target_lang='ja'  # space=False is default
)
```

#### Advanced Usage

```python
from subtranslate.core.main import SubtitleTranslator

translator = SubtitleTranslator(api_key="YOUR_API_KEY")
translator.translate_file(
    input_file="sample.en.srt",
    output_file="sample_en_fr_both.srt",
    src_lang="en",
    target_lang="fr",
    encoding="UTF-8",
    mode="split",
    both=True,
    space=True,
    resume=True  # Enable resume functionality
)
```

## ⚙️ How it Works

SubtranSlate processes subtitle files through these steps:

1. **Parsing**: Extract subtitle entries, including timing and text content
2. **Sentence Splitting**: Split text into complete sentences for better translation quality
3. **Translation**: Translate sentences using Google Translate service
4. **Reconstruction**: Recombine and align translated sentences with original subtitle timing
5. **Output**: Save the result as a new SRT file

The **split mode** provides context-aware translations by treating sentences that span multiple subtitles as a single unit.
The **naive mode** translates each subtitle entry independently.

## 🛡️ Rate Limiting Protection

SubtranSlate includes robust protection against rate limiting:

### Advanced Retry Mechanism

- Detects rate limit errors (HTTP 429) and server errors (5xx)
- Implements exponential backoff with jitter
- Rotates user agents between retry attempts
- Configurable retry parameters

### Checkpoint & Resume System

- Creates checkpoint files to track translation progress
- Supports resuming translation from the last successful point
- Preserves partially translated content

### Batch Processing Resilience

- Maintains a batch state file tracking progress across multiple files
- Automatically pauses and continues when rate limited
- Skips already completed files on subsequent runs

### Best Practices for Large Files

1. **Use an API Key**: Higher quotas with Google Cloud Translation API
2. **Split Large Jobs**: Break very large files into smaller chunks
3. **Use Batch Mode**: Enable the resume feature for reliability
4. **Choose Off-Peak Hours**: Run large translation jobs when servers are less busy

## 📋 Output Examples

### Original Subtitle

```
1
00:00:00,000 --> 00:00:02,430
Coding has been
the bread and butter for
2
00:00:02,430 --> 00:00:04,290
developers since
the dawn of computing.
```

### Translated to Chinese

```
1
00:00:00,000 --> 00:00:02,430
自计算机开始以来，编码
Coding has been the bread and butter for
2
00:00:02,430 --> 00:00:04,290
一直是开发人员的必需品。
developers since the dawn of computing.
```

### Translated to Japanese

```
1
00:00:00,000 --> 00:00:02,430
コーディングは、コンピューティングの夜
Coding has been the bread and butter for
2
00:00:02,430 --> 00:00:04,290
明け以来、開発者にとって重要な要素です。
developers since the dawn of computing.
```

## 🌐 Supported Languages

The project supports translation between many languages including:

| Language | Code |
|----------|------|
| Arabic | ar |
| Chinese (Simplified) | zh-CN |
| Chinese (Traditional) | zh-TW |
| Dutch | nl |
| English | en |
| French | fr |
| German | de |
| Hindi | hi |
| Italian | it |
| Japanese | ja |
| Korean | ko |
| Portuguese | pt |
| Russian | ru |
| Spanish | es |
| Turkish | tr |
| Vietnamese | vi |

For a complete list of language codes, see [Google Cloud Translation Languages](https://cloud.google.com/translate/docs/languages)

### Language Handling Notes

- For languages using spaces between words (English, French, etc.), set `space=True`
- For languages not using spaces (Chinese, Japanese, etc.), keep `space=False` (default)
- For Chinese translations, the `jieba` library improves quality through word segmentation

## 🔤 Supported Encodings

SubtranSlate supports a wide range of character encodings for subtitle files:

### Common Subtitle Encodings

| Region | Encodings |
|--------|-----------|
| Thai | UTF-8, TIS-620, CP874, ISO8859-11 |
| Chinese | UTF-8, GB2312, CP936 (Simplified), Big5, CP950 (Traditional) |
| Japanese | UTF-8, Shift-JIS, EUC-JP, CP932 |
| Korean | UTF-8, EUC-KR, CP949 |
| Cyrillic | UTF-8, CP1251, KOI8-R, ISO8859-5 |
| Arabic | UTF-8, CP1256, ISO8859-6 |
| Hebrew | UTF-8, CP1255, ISO8859-8 |
| Western European | UTF-8, CP1252, ISO8859-1, ISO8859-15 |
| Central European | UTF-8, CP1250, ISO8859-2 |
| Greek | UTF-8, CP1253, ISO8859-7 |
| Turkish | UTF-8, CP1254, ISO8859-9 |
| Vietnamese | UTF-8, CP1258 |

### UTF-8 Variants

- UTF-8 - Standard encoding for Unicode
- UTF-8-sig - UTF-8 with Byte Order Mark (BOM)

For the complete list of supported encodings, use the `subtranslate encode --list-encodings` command.

## ❓ Troubleshooting

### Encoding Issues

If you encounter encoding problems with subtitle files:

1. Try auto-detecting the encoding:
   ```bash
   subtranslate encode problem_file.srt
   ```

2. Try a specific encoding for Asian languages:
   ```bash
   subtranslate translate input.srt output.srt --encoding cp874
   ```

3. Convert to a different encoding:
   ```bash
   subtranslate encode input.srt --to-encoding utf-8-sig
   ```

4. For Thai subtitles specifically:
   ```bash
   subtranslate encode thai_subtitle.srt --to-encoding tis-620
   ```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
