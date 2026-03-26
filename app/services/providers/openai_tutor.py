from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import ValidationError

from ...config import Settings
from ...models.domain import SessionRecord, TutorTurnPayload
from ...prompts import TUTOR_JSON_SCHEMA, build_system_prompt, build_user_prompt
from .base import TutorProvider

logger = logging.getLogger(__name__)


class OpenAITutorProvider(TutorProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.http = httpx.AsyncClient(
            base_url="https://api.openai.com",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(90.0, connect=15.0),
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    async def generate_turn(self, session: SessionRecord, learner_english: str) -> TutorTurnPayload:
        body = {
            "model": self.settings.openai_model,
            "store": False,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": build_system_prompt(session)}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": build_user_prompt(session, learner_english)}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "language_tutor_turn",
                    "strict": True,
                    "schema": TUTOR_JSON_SCHEMA,
                }
            },
        }

        response = await self.http.post("/v1/responses", json=body)
        response.raise_for_status()
        request_id = response.headers.get("x-request-id")
        if request_id:
            logger.info("OpenAI Responses request_id=%s model=%s", request_id, self.settings.openai_model)

        payload = response.json()
        output_text = self._extract_output_text(payload)
        if not output_text:
            raise RuntimeError("OpenAI returned an empty tutor response.")

        try:
            return TutorTurnPayload.model_validate_json(output_text)
        except ValidationError as exc:
            logger.exception("Failed to validate OpenAI structured output: %s", output_text)
            raise RuntimeError(f"Could not validate OpenAI structured response: {exc}") from exc

    def _extract_output_text(self, payload: dict[str, Any]) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct

        for item in payload.get("output") or []:
            if item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        return ""
