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


def test_health_and_index(monkeypatch):
    with make_client(monkeypatch) as client:
        health = client.get("/api/healthz")
        assert health.status_code == 200
        assert health.json()["mock_mode"] is True

        index = client.get("/")
        assert index.status_code == 200
        assert "Atlas Lingua" in index.text
        assert "Speak in English" in index.text


def test_session_typed_turn_summary_topics(monkeypatch):
    with make_client(monkeypatch) as client:
        create = client.post(
            "/api/sessions",
            json={"target_language": "es", "difficulty": "beginner"},
        )
        assert create.status_code == 200
        session = create.json()
        session_id = session["id"]
        assert session["mock_mode"] is True
        assert session["target_language"] == "es"

        turn = client.post(
            f"/api/sessions/{session_id}/typed-turn",
            json={"text": "I would like to order a coffee, please."},
        )
        assert turn.status_code == 200
        turn_payload = turn.json()["turn"]
        assert turn_payload["user_english"] == "I would like to order a coffee, please."
        assert "café" in turn_payload["user_target"].lower()
        assert turn_payload["tutor_target"]

        get_session = client.get(f"/api/sessions/{session_id}")
        assert get_session.status_code == 200
        assert len(get_session.json()["turns"]) == 1

        end = client.post(f"/api/sessions/{session_id}/end")
        assert end.status_code == 200
        assert end.json()["ended_at"] is not None

        summary = client.post(f"/api/sessions/{session_id}/summary")
        assert summary.status_code == 200
        assert summary.json()["summary_text"].startswith("Mock summary")

        topics = client.post(f"/api/sessions/{session_id}/topics")
        assert topics.status_code == 200
        assert topics.json()["topics"]


def test_audio_turn_upload(monkeypatch):
    with make_client(monkeypatch) as client:
        create = client.post(
            "/api/sessions",
            json={"target_language": "fr", "difficulty": "beginner"},
        )
        assert create.status_code == 200
        session_id = create.json()["id"]

        upload = client.post(
            f"/api/sessions/{session_id}/audio-turn",
            files={"audio": ("turn.webm", b"fake audio bytes", "audio/webm")},
        )
        assert upload.status_code == 200
        payload = upload.json()["turn"]
        assert payload["user_english"]
        assert payload["user_target"]
        assert payload["tutor_target"]


def test_settings_accept_blank_optional_threshold(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("FLUX_EAGER_EOT_THRESHOLD", "")
    from app.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.flux_eager_eot_threshold is None
