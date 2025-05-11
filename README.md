# SubtranSlate

A powerful and flexible tool for translating subtitle files between languages. Currently supports SRT format.

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.6+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

</div>

## 📋 Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
  - [Command-Line Interface](#command-line-interface)
  - [Examples](#examples)
  - [Programmatic Usage](#programmatic-usage)
- [How it Works](#how-it-works)
- [Rate Limiting Protection](#rate-limiting-protection)
- [Supported Languages](#supported-languages)
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
  - Support for various text encodings (UTF-8, UTF-8-sig, etc.)
  - Optional Google Cloud Translation API integration
  - Display original and translated text together or only translations
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

```bash
subtranslate [options] input_file output_file
```

Or if running from source:

```bash
python run.py [options] input_file output_file
```

#### CLI Options

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

## ❓ Troubleshooting

### Encoding Issues

If you encounter encoding problems:

```bash
subtranslate sample.en.srt output.srt --encoding UTF-8-sig
```

### Character Limits

For long subtitle files, be aware that Google Translate has character limits. The application automatically splits large files into smaller chunks.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
