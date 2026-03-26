from __future__ import annotations

from fastapi import Request

from ..services.conversation_orchestrator import ConversationOrchestrator



def get_orchestrator(request: Request) -> ConversationOrchestrator:
    return request.app.state.orchestrator
