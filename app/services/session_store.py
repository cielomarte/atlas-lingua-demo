from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import HTTPException, status

from ..models.domain import ConversationTurn, SessionRecord, TopicHit



def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, session: SessionRecord) -> SessionRecord:
        async with self._lock:
            self._sessions[session.id] = session.model_copy(deep=True)
            return self._sessions[session.id].model_copy(deep=True)

    async def get(self, session_id: str) -> SessionRecord:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            return session.model_copy(deep=True)

    async def add_turn(self, session_id: str, turn: ConversationTurn) -> SessionRecord:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            session.turns.append(turn)
            self._sessions[session_id] = session
            return session.model_copy(deep=True)

    async def end(self, session_id: str) -> SessionRecord:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            session.ended_at = utc_now()
            self._sessions[session_id] = session
            return session.model_copy(deep=True)

    async def set_summary(self, session_id: str, summary_text: str) -> SessionRecord:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            session.summary_text = summary_text
            self._sessions[session_id] = session
            return session.model_copy(deep=True)

    async def set_topics(self, session_id: str, topics: list[TopicHit]) -> SessionRecord:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
            session.topics = topics
            self._sessions[session_id] = session
            return session.model_copy(deep=True)
