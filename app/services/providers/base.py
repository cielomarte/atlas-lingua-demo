from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from fastapi import WebSocket

from ...models.domain import SessionRecord, TopicHit, TutorTurnPayload

EventCallback = Callable[[dict], Awaitable[None]]


class SpeechProvider(ABC):
    @abstractmethod
    async def stream_turn(
        self,
        browser_ws: WebSocket,
        session: SessionRecord,
        on_event: EventCallback,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def transcribe_bytes(self, audio_bytes: bytes, content_type: str | None = None, filename: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    async def synthesize(self, text: str, voice_model: str) -> tuple[bytes | None, str | None, str | None]:
        raise NotImplementedError

    @abstractmethod
    async def summarize(self, text: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def detect_topics(self, text: str) -> list[TopicHit]:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


class TutorProvider(ABC):
    @abstractmethod
    async def generate_turn(self, session: SessionRecord, learner_english: str) -> TutorTurnPayload:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None
