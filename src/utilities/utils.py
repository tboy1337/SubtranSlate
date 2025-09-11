"""Utilities module for subtitle processing."""

from typing import Protocol

import srt

from .util_srt import (
    compute_mass_list,
    sen_list2dialog_list,
    split_and_record,
    triple_r,
)
from .util_trans import Translator


class SubtitleLike(Protocol):
    """Protocol for subtitle objects with required attributes."""

    content: str


# Type alias for better clarity
SubtitleList = list[SubtitleLike]


def simple_translate_srt(
    origin_sub: SubtitleList, src_lang: str, target_lang: str
) -> list[str]:
    """
    Naive srt translation
    :param origin_sub: list of srt.Subtitle
    :param src_lang: source language. the ISO-639-1 language code of the input text
    :param target_lang: target language. the ISO-639-1 language code of the output text
    :return: translated subtitle content list
    """
    # Initialize a translator
    translator = Translator()

    sen_list = [sub.content.replace("\n", "") for sub in origin_sub]

    # Translate the subtitle and split into list
    translated_sen: str = translator.translate_lines(sen_list, src_lang, target_lang)
    translated_sen_list: list[str] = translated_sen.split("\n")

    return translated_sen_list


def translate_srt(
    origin_sub: SubtitleList, src_lang: str, target_lang: str, space: bool = False
) -> list[str]:
    """
    Translate the srt
        Afrikaans af, Albanian sq, Amharic am, Arabic ar, Armenian hy, Azerbaijani az
        Basque eu, Belarusian be, Bengali bn, Bosnian bs, Bulgarian bg, Catalan ca
        Cebuano ceb, Chinese(Simplified) zh-CN, Chinese (Traditional) zh-TW
        Corsican co, Croatian hr, Czech cs, Danish da, Dutch nl, English en
        Esperanto eo, Estonian et, Finnish fi, French fr, Frisian fy, Galician gl
        Georgian ka, German de, Greek el, Gujarati gu, Haitian Creole ht, Hausa ha
        Hawaiian haw, Hebrew he, Hindi hi, Hmong hmn, Hungarian hu, Icelandic is
        Igbo ig, Indonesian id, Irish ga, Italian it, Japanese ja, Javanese jw
        ...
        Explore more google translate supported language please visit:
        https://cloud.google.com/translate/docs/languages

    English, French, German ... are the language that split each word in a sentence by space
    Chinese, Japanese are NOT the language that split each word in a sentence by space

    :param origin_sub: list of srt.Subtitle
    :param src_lang: source language. the ISO-639-1 language code of the input text
    :param target_lang: target language. the ISO-639-1 language code of the output text
    :param space: is the vocabulary of target language split by space
    :return: translated subtitle content list
    """
    # Initialize a translator
    translator = Translator()

    # Reconstruct plain text of the whole subtitle file.
    # Record the index of each dialogue in the plain text.
    plain_text, dialog_idx = triple_r(origin_sub)

    # Split the plain text into sentences.
    # Record the index of each sentence in the plain text.
    sen_list, sen_idx = split_and_record(plain_text)

    # Translate the subtitle and split into list
    translated_sen = translator.translate_lines(sen_list, src_lang, target_lang)
    translated_sen_list = translated_sen.split("\n")

    # Compute the mass list
    mass_list = compute_mass_list(dialog_idx, sen_idx)

    # split the translated_sen by the timestamp in the srt file
    is_chinese = target_lang == "zh-CN"
    dialog_list: list[str] = sen_list2dialog_list(
        translated_sen_list, mass_list, space, is_chinese=is_chinese
    )

    return dialog_list


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
) -> None:
    """
    Translate the srt file
        Afrikaans af, Albanian sq, Amharic am, Arabic ar, Armenian hy, Azerbaijani az
        Basque eu, Belarusian be, Bengali bn, Bosnian bs, Bulgarian bg, Catalan ca
        Cebuano ceb, Chinese(Simplified) zh-CN, Chinese (Traditional) zh-TW
        Corsican co, Croatian hr, Czech cs, Danish da, Dutch nl, English en
        Esperanto eo, Estonian et, Finnish fi, French fr, Frisian fy, Galician gl
        Georgian ka, German de, Greek el, Gujarati gu, Haitian Creole ht, Hausa ha
        Hawaiian haw, Hebrew he, Hindi hi, Hmong hmn, Hungarian hu, Icelandic is
        Igbo ig, Indonesian id, Irish ga, Italian it, Japanese ja, Javanese jw
        ...
        Explore more google translate supported language please visit:
        https://cloud.google.com/translate/docs/languages

    English, French, German ... are the language that split each word in a sentence by space
    Chinese, Japanese are NOT the language that split each word in a sentence by space

    mode: 'naive' or 'split'
    both: if it is True, save both src_lang and target_lang, otherwise save only target_lang
    :param input_file: input file path, only srt file supported currently
    :param output_file: output file path
    :param src_lang: source language. the ISO-639-1 language code of the input text
    :param target_lang: target language. the ISO-639-1 language code of the output text
    :param encoding: encoding of the input file
    :param mode: 'naive' or 'split'
    :param both: save both src_lang and target_lang or target_lang only
    :param space: is the vocabulary of target language split by space
    :return: None
    """
    with open(input_file, encoding=encoding) as srt_file:
        subtitle = list(srt.parse(srt_file.read()))

    if mode == "naive":
        translated_list = simple_translate_srt(subtitle, src_lang, target_lang)
    else:
        translated_list = translate_srt(subtitle, src_lang, target_lang, space=space)

    if len(subtitle) == len(translated_list):
        if both:
            for i, sub in enumerate(subtitle):
                sub.content = translated_list[i] + "\n" + sub.content.replace("\n", " ")
        else:
            for i, sub in enumerate(subtitle):
                sub.content = translated_list[i]
    else:
        print("Error")
        return

    with open(output_file, "w", encoding="UTF-8") as f:
        f.write(srt.compose(subtitle))
