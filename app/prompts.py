from __future__ import annotations

import json
from typing import Any

from .catalog import SUPPORTED_LANGUAGES
from .models.domain import SessionRecord


TUTOR_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "translated_user_utterance": {
            "type": "string",
            "description": "Natural translation of the learner's English utterance into the target language.",
        },
        "translated_user_utterance_romanized": {
            "type": "string",
            "description": "Romanization when helpful, especially for Japanese. Use an empty string otherwise.",
        },
        "tutor_reply_target": {
            "type": "string",
            "description": "A short tutor response that continues the conversation in the target language.",
        },
        "tutor_reply_english_hint": {
            "type": "string",
            "description": "A concise English gloss for the tutor reply.",
        },
        "teacher_note": {
            "type": "string",
            "description": "One short teaching note about grammar, register, or pronunciation. Use an empty string when unnecessary.",
        },
        "vocabulary": {
            "type": "array",
            "description": "Zero to three useful vocabulary items from this turn.",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["word", "meaning"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "translated_user_utterance",
        "translated_user_utterance_romanized",
        "tutor_reply_target",
        "tutor_reply_english_hint",
        "teacher_note",
        "vocabulary",
    ],
    "additionalProperties": False,
}


def build_system_prompt(session: SessionRecord) -> str:
    language = SUPPORTED_LANGUAGES[session.target_language]
    return (
        "You are a patient spoken-language tutor. "
        "The learner always speaks English. "
        f"The target language is {language.label} ({language.code}). "
        f"The difficulty level is {session.difficulty.value}. "
        "Translate the learner's latest English utterance naturally into the target language. "
        "Then continue the conversation with one short tutor reply in the target language. "
        "Keep the tutor reply supportive, conversational, and under 24 words. "
        "The English hint should be concise and natural. "
        "teacher_note should be brief and optional. "
        "vocabulary should contain at most three useful items. "
        "Return romanization only when useful, especially for Japanese, else empty string."
    )


def build_user_prompt(session: SessionRecord, learner_english: str) -> str:
    history_lines: list[str] = []
    for turn in session.turns[-6:]:
        history_lines.append(f"Learner (English): {turn.user_english}")
        history_lines.append(f"Tutor ({session.target_language}): {turn.tutor_target}")
        history_lines.append(f"Tutor hint (English): {turn.tutor_english_hint}")

    history_blob = "\n".join(history_lines) if history_lines else "No previous turns yet."
    payload = {
        "target_language": session.target_language,
        "difficulty": session.difficulty.value,
        "conversation_history": history_blob,
        "latest_learner_english": learner_english,
        "output_contract": {
            "translated_user_utterance": "required string",
            "translated_user_utterance_romanized": "required string; empty if not needed",
            "tutor_reply_target": "required string",
            "tutor_reply_english_hint": "required string",
            "teacher_note": "required string; empty if none",
            "vocabulary": "required array of {word, meaning}; up to 3",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_intelligence_transcript(session: SessionRecord) -> str:
    lines: list[str] = []
    for index, turn in enumerate(session.turns, start=1):
        lines.append(f"Turn {index}")
        lines.append(f"Learner: {turn.user_english}")
        lines.append(f"Tutor: {turn.tutor_english_hint}")
        if turn.teacher_note:
            lines.append(f"Teacher note: {turn.teacher_note}")
    return "\n".join(lines).strip()
