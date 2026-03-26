from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile

from ..models.api import (
    BootstrapResponse,
    SessionCreateRequest,
    SessionResponse,
    SummaryResponse,
    TopicsResponse,
    TurnResponse,
    TypedTurnRequest,
)
from ..services.conversation_orchestrator import ConversationOrchestrator
from .deps import get_orchestrator

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/healthz")
async def healthz(request: Request) -> dict:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "mock_mode": settings.effective_mock_mode,
    }


@router.get("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(orchestrator: ConversationOrchestrator = Depends(get_orchestrator)) -> BootstrapResponse:
    return orchestrator.bootstrap_payload()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    payload: SessionCreateRequest,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> SessionResponse:
    return await orchestrator.create_session(payload.target_language, payload.difficulty)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> SessionResponse:
    return await orchestrator.get_session(session_id)


@router.post("/sessions/{session_id}/typed-turn", response_model=TurnResponse)
async def typed_turn(
    session_id: str,
    payload: TypedTurnRequest,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> TurnResponse:
    turn = await orchestrator.process_transcript(session_id, payload.text.strip())
    return TurnResponse(turn=turn)


@router.post("/sessions/{session_id}/audio-turn", response_model=TurnResponse)
async def audio_turn(
    session_id: str,
    audio: UploadFile = File(...),
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> TurnResponse:
    audio_bytes = await audio.read()
    turn = await orchestrator.process_audio_upload(
        session_id,
        audio_bytes,
        content_type=audio.content_type,
        filename=audio.filename,
    )
    return TurnResponse(turn=turn)


@router.post("/sessions/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: str,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> SessionResponse:
    return await orchestrator.end_session(session_id)


@router.post("/sessions/{session_id}/summary", response_model=SummaryResponse)
async def summarize_session(
    session_id: str,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> SummaryResponse:
    return await orchestrator.summarize_session(session_id)


@router.post("/sessions/{session_id}/topics", response_model=TopicsResponse)
async def topics_for_session(
    session_id: str,
    orchestrator: ConversationOrchestrator = Depends(get_orchestrator),
) -> TopicsResponse:
    return await orchestrator.topics_for_session(session_id)
