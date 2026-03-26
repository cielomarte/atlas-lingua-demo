from __future__ import annotations

from fastapi import HTTPException, status

from ..catalog import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, language_choices
from ..config import Settings
from ..models.api import BootstrapResponse, SessionResponse, SummaryResponse, TopicsResponse
from ..models.domain import ConversationTurn, DifficultyLevel, SessionRecord
from ..prompts import build_intelligence_transcript
from .audio_storage import AudioStorage
from .providers.base import SpeechProvider, TutorProvider
from .session_store import SessionStore


class ConversationOrchestrator:
    def __init__(
        self,
        settings: Settings,
        session_store: SessionStore,
        speech_provider: SpeechProvider,
        tutor_provider: TutorProvider,
        audio_storage: AudioStorage,
    ) -> None:
        self.settings = settings
        self.session_store = session_store
        self.speech_provider = speech_provider
        self.tutor_provider = tutor_provider
        self.audio_storage = audio_storage

    def bootstrap_payload(self) -> BootstrapResponse:
        return BootstrapResponse(
            app_name=self.settings.app_name,
            app_tagline=self.settings.app_tagline,
            mock_mode=self.settings.effective_mock_mode,
            languages=language_choices(),
            default_language=DEFAULT_LANGUAGE,
            default_difficulty=DifficultyLevel.beginner.value,
        )

    async def create_session(self, target_language: str, difficulty: DifficultyLevel) -> SessionResponse:
        if target_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported target language")
        option = SUPPORTED_LANGUAGES[target_language]
        session = SessionRecord(
            target_language=option.code,
            voice_model=option.voice_model,
            speech_lang_tag=option.speech_lang_tag,
            difficulty=difficulty,
        )
        created = await self.session_store.create(session)
        return self._to_session_response(created)

    async def get_session(self, session_id: str) -> SessionResponse:
        session = await self.session_store.get(session_id)
        return self._to_session_response(session)

    async def end_session(self, session_id: str) -> SessionResponse:
        ended = await self.session_store.end(session_id)
        return self._to_session_response(ended)

    async def process_transcript(self, session_id: str, learner_english: str) -> ConversationTurn:
        session = await self.session_store.get(session_id)
        if session.is_ended:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session has already ended")

        tutor_payload = await self.tutor_provider.generate_turn(session, learner_english)

        user_audio_url = None
        tutor_audio_url = None
        user_audio_fallback = tutor_payload.translated_user_utterance
        tutor_audio_fallback = tutor_payload.tutor_reply_target

        user_audio_bytes, _user_content_type, user_ext = await self.speech_provider.synthesize(
            tutor_payload.translated_user_utterance,
            session.voice_model,
        )
        if user_audio_bytes and user_ext:
            user_audio_url = self.audio_storage.save_bytes(session_id, "learner", user_audio_bytes, user_ext)

        tutor_audio_bytes, _tutor_content_type, tutor_ext = await self.speech_provider.synthesize(
            tutor_payload.tutor_reply_target,
            session.voice_model,
        )
        if tutor_audio_bytes and tutor_ext:
            tutor_audio_url = self.audio_storage.save_bytes(session_id, "tutor", tutor_audio_bytes, tutor_ext)

        turn = ConversationTurn(
            user_english=learner_english,
            user_target=tutor_payload.translated_user_utterance,
            user_target_romanized=tutor_payload.translated_user_utterance_romanized,
            user_audio_url=user_audio_url,
            user_audio_fallback_text=user_audio_fallback,
            tutor_target=tutor_payload.tutor_reply_target,
            tutor_english_hint=tutor_payload.tutor_reply_english_hint,
            tutor_audio_url=tutor_audio_url,
            tutor_audio_fallback_text=tutor_audio_fallback,
            teacher_note=tutor_payload.teacher_note,
            vocabulary=tutor_payload.vocabulary,
        )
        await self.session_store.add_turn(session_id, turn)
        return turn

    async def process_audio_upload(self, session_id: str, audio_bytes: bytes, content_type: str | None = None, filename: str | None = None) -> ConversationTurn:
        session = await self.session_store.get(session_id)
        if session.is_ended:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session has already ended")
        transcript = await self.speech_provider.transcribe_bytes(audio_bytes, content_type=content_type, filename=filename)
        transcript = transcript.strip()
        if not transcript:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No speech was detected in the uploaded audio")
        return await self.process_transcript(session_id, transcript)

    async def summarize_session(self, session_id: str) -> SummaryResponse:
        session = await self.session_store.get(session_id)
        transcript = build_intelligence_transcript(session)
        if not transcript:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No conversation to summarize")
        summary_text = await self.speech_provider.summarize(transcript)
        await self.session_store.set_summary(session_id, summary_text)
        return SummaryResponse(session_id=session_id, summary_text=summary_text)

    async def topics_for_session(self, session_id: str) -> TopicsResponse:
        session = await self.session_store.get(session_id)
        transcript = build_intelligence_transcript(session)
        if not transcript:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No conversation to analyze")
        topics = await self.speech_provider.detect_topics(transcript)
        await self.session_store.set_topics(session_id, topics)
        return TopicsResponse(session_id=session_id, topics=topics)

    def _to_session_response(self, session: SessionRecord) -> SessionResponse:
        return SessionResponse(
            id=session.id,
            created_at=session.created_at,
            ended_at=session.ended_at,
            target_language=session.target_language,
            voice_model=session.voice_model,
            speech_lang_tag=session.speech_lang_tag,
            difficulty=session.difficulty,
            turns=session.turns,
            summary_text=session.summary_text,
            topics=session.topics,
            mock_mode=self.settings.effective_mock_mode,
        )
