from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .domain import ConversationTurn, DifficultyLevel, LanguageOption, TopicHit


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_language: str
    difficulty: DifficultyLevel = DifficultyLevel.beginner


class TypedTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)


class TurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn: ConversationTurn


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    created_at: datetime
    ended_at: datetime | None
    target_language: str
    voice_model: str
    speech_lang_tag: str
    difficulty: DifficultyLevel
    turns: list[ConversationTurn]
    summary_text: str | None = None
    topics: list[TopicHit] = Field(default_factory=list)
    mock_mode: bool = False


class SummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    summary_text: str


class TopicsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    topics: list[TopicHit] = Field(default_factory=list)


class BootstrapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_name: str
    app_tagline: str
    mock_mode: bool
    default_language: str
    default_difficulty: str
    languages: list[LanguageOption]
