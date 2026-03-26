from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field



def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DifficultyLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class LanguageOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    voice_model: str
    speech_lang_tag: str
    showcase_phrase: str


class VocabularyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str
    meaning: str


class TutorTurnPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translated_user_utterance: str = Field(min_length=1)
    translated_user_utterance_romanized: str = ""
    tutor_reply_target: str = Field(min_length=1)
    tutor_reply_english_hint: str = Field(min_length=1)
    teacher_note: str = ""
    vocabulary: list[VocabularyItem] = Field(default_factory=list)


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=utc_now)

    user_english: str
    user_target: str
    user_target_romanized: str = ""
    user_audio_url: str | None = None
    user_audio_fallback_text: str | None = None

    tutor_target: str
    tutor_english_hint: str
    tutor_audio_url: str | None = None
    tutor_audio_fallback_text: str | None = None

    teacher_note: str = ""
    vocabulary: list[VocabularyItem] = Field(default_factory=list)


class TopicHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    confidence_score: float
    source_text: str = ""


class SessionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None

    target_language: str
    voice_model: str
    speech_lang_tag: str
    difficulty: DifficultyLevel

    turns: list[ConversationTurn] = Field(default_factory=list)
    summary_text: str | None = None
    topics: list[TopicHit] = Field(default_factory=list)

    @property
    def is_ended(self) -> bool:
        return self.ended_at is not None
