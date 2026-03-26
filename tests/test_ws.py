from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def make_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    app = create_app()
    return TestClient(app)


def test_websocket_turn_flow(monkeypatch):
    with make_client(monkeypatch) as client:
        create = client.post(
            "/api/sessions",
            json={"target_language": "ja", "difficulty": "beginner"},
        )
        session_id = create.json()["id"]

        with client.websocket_connect(f"/ws/sessions/{session_id}/turn") as ws:
            ws.send_bytes(b"dummy audio bytes")
            ws.send_text('{"type":"finalize"}')

            seen_turn_complete = None
            while True:
                payload = ws.receive_json()
                if payload["type"] == "turn_complete":
                    seen_turn_complete = payload["turn"]
                    break

            assert seen_turn_complete is not None
            assert seen_turn_complete["user_english"]
            assert seen_turn_complete["tutor_target"]
            assert seen_turn_complete["user_target"]
