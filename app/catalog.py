from __future__ import annotations

from typing import Final

from .models.domain import LanguageOption


SUPPORTED_LANGUAGES: Final[dict[str, LanguageOption]] = {
    "en": LanguageOption(
        code="en",
        label="English",
        voice_model="aura-2-thalia-en",
        speech_lang_tag="en-US",
        showcase_phrase="I would like a coffee, please.",
    ),
    "es": LanguageOption(
        code="es",
        label="Spanish",
        voice_model="aura-2-javier-es",
        speech_lang_tag="es-ES",
        showcase_phrase="Me gustaría un café, por favor.",
    ),
    "de": LanguageOption(
        code="de",
        label="German",
        voice_model="aura-2-viktoria-de",
        speech_lang_tag="de-DE",
        showcase_phrase="Ich hätte gern einen Kaffee, bitte.",
    ),
    "fr": LanguageOption(
        code="fr",
        label="French",
        voice_model="aura-2-agathe-fr",
        speech_lang_tag="fr-FR",
        showcase_phrase="Je voudrais un café, s'il vous plaît.",
    ),
    "nl": LanguageOption(
        code="nl",
        label="Dutch",
        voice_model="aura-2-rhea-nl",
        speech_lang_tag="nl-NL",
        showcase_phrase="Ik zou graag een koffie willen, alstublieft.",
    ),
    "it": LanguageOption(
        code="it",
        label="Italian",
        voice_model="aura-2-livia-it",
        speech_lang_tag="it-IT",
        showcase_phrase="Vorrei un caffè, per favore.",
    ),
    "ja": LanguageOption(
        code="ja",
        label="Japanese",
        voice_model="aura-2-izanami-ja",
        speech_lang_tag="ja-JP",
        showcase_phrase="コーヒーをお願いします。",
    ),
}


DEFAULT_LANGUAGE = "es"


def language_choices() -> list[LanguageOption]:
    return [SUPPORTED_LANGUAGES[key] for key in sorted(SUPPORTED_LANGUAGES.keys())]
