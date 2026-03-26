from __future__ import annotations

import contextlib
import logging

from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from ..services.conversation_orchestrator import ConversationOrchestrator

logger = logging.getLogger(__name__)


async def _safe_send_json(websocket: WebSocket, payload: dict) -> None:
    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.send_json(payload)


def register_ws_routes(app: FastAPI) -> None:
    @app.websocket("/ws/sessions/{session_id}/turn")
    async def stream_turn(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        orchestrator: ConversationOrchestrator = app.state.orchestrator
        speech_provider = app.state.speech_provider

        try:
            session = await orchestrator.session_store.get(session_id)
            if session.is_ended:
                await _safe_send_json(websocket, {"type": "error", "message": "This session has already ended."})
                return

            async def on_event(payload: dict) -> None:
                await _safe_send_json(websocket, payload)

            transcript = await speech_provider.stream_turn(websocket, session, on_event)
            transcript = transcript.strip()
            if not transcript:
                await _safe_send_json(websocket, {"type": "error", "message": "No speech was detected. Please try again."})
                return

            await _safe_send_json(
                websocket,
                {"type": "status", "status": "processing", "message": "Generating translation and tutor reply…"},
            )
            turn = await orchestrator.process_transcript(session_id, transcript)
            await _safe_send_json(websocket, {"type": "turn_complete", "turn": turn.model_dump(mode="json")})
        except WebSocketDisconnect:
            logger.info("Browser websocket disconnected for session %s", session_id)
        except Exception as exc:
            logger.exception("Turn stream failed for session %s", session_id)
            with contextlib.suppress(Exception):
                await _safe_send_json(websocket, {"type": "error", "message": str(exc)})
        finally:
            if websocket.client_state == WebSocketState.CONNECTED:
                with contextlib.suppress(Exception):
                    await websocket.close()
