from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api import api_router, register_ws_routes
from .config import Settings, get_settings
from .services import AudioStorage, ConversationOrchestrator, SessionStore
from .services.providers import (
    DeepgramSpeechProvider,
    MockSpeechProvider,
    MockTutorProvider,
    OpenAITutorProvider,
)


STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        session_store = SessionStore()
        audio_storage = AudioStorage(settings.media_root_resolved)

        if settings.effective_mock_mode:
            speech_provider = MockSpeechProvider()
            tutor_provider = MockTutorProvider()
        else:
            speech_provider = DeepgramSpeechProvider(settings)
            tutor_provider = OpenAITutorProvider(settings)

        orchestrator = ConversationOrchestrator(
            settings=settings,
            session_store=session_store,
            speech_provider=speech_provider,
            tutor_provider=tutor_provider,
            audio_storage=audio_storage,
        )

        app.state.settings = settings
        app.state.templates = templates
        app.state.session_store = session_store
        app.state.audio_storage = audio_storage
        app.state.speech_provider = speech_provider
        app.state.tutor_provider = tutor_provider
        app.state.orchestrator = orchestrator
        yield
        await speech_provider.aclose()
        await tutor_provider.aclose()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        debug=settings.debug,
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.mount("/media", StaticFiles(directory=str(settings.media_root_resolved)), name="media")
    app.include_router(api_router)
    register_ws_routes(app)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        bootstrap = request.app.state.orchestrator.bootstrap_payload().model_dump(mode="json")
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "page_title": settings.ui_title,
                "settings": settings,
                "bootstrap_json": json.dumps(bootstrap, ensure_ascii=False),
            },
        )

    return app

