from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx
import websockets
from fastapi import WebSocket
from websockets.client import ClientConnection
from websockets.exceptions import ConnectionClosed

from ...config import Settings
from ...models.domain import SessionRecord, TopicHit
from .base import EventCallback, SpeechProvider

logger = logging.getLogger(__name__)

TURN_EVENTS = {"StartOfTurn", "Update", "EagerEndOfTurn", "TurnResumed", "EndOfTurn"}


class DeepgramSpeechProvider(SpeechProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.http = httpx.AsyncClient(
            base_url="https://api.deepgram.com",
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
            },
            timeout=httpx.Timeout(90.0, connect=15.0),
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    async def stream_turn(
        self,
        browser_ws: WebSocket,
        session: SessionRecord,
        on_event: EventCallback,
    ) -> str:
        params: dict[str, Any] = {
            "model": self.settings.flux_model,
            "encoding": "linear16",
            "sample_rate": 16000,
            "channels": 1,
            "eot_threshold": self.settings.flux_eot_threshold,
            "eot_timeout_ms": self.settings.flux_eot_timeout_ms,
            "punctuate": "true",
            "smart_format": "true",
        }
        if self.settings.flux_eager_eot_threshold is not None:
            params["eager_eot_threshold"] = self.settings.flux_eager_eot_threshold

        dg_url = f"wss://api.deepgram.com/v2/listen?{urlencode(params)}"
        latest_transcript = ""
        await on_event({"type": "status", "status": "connecting", "message": "Connecting to Deepgram Flux…"})

        async with websockets.connect(
            dg_url,
            additional_headers={"Authorization": f"Token {self.settings.deepgram_api_key}"},
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
            open_timeout=15,
        ) as dg_ws:
            bridge_task = asyncio.create_task(self._pipe_browser_to_deepgram(browser_ws, dg_ws))
            try:
                await on_event({"type": "status", "status": "listening", "message": "Listening…"})
                while True:
                    try:
                        raw_message = await dg_ws.recv()
                    except ConnectionClosed:
                        break

                    if isinstance(raw_message, bytes):
                        continue

                    payload = json.loads(raw_message)
                    message_type = payload.get("type")
                    event_name = payload.get("event") or message_type or "Unknown"

                    if message_type == "Metadata":
                        request_id = payload.get("request_id")
                        logger.info("Deepgram Flux connected request_id=%s", request_id)
                        await on_event(
                            {
                                "type": "status",
                                "status": "listening",
                                "message": "Listening…",
                                "request_id": request_id,
                            }
                        )
                        continue

                    if message_type == "TurnInfo" and event_name in TURN_EVENTS:
                        transcript = (payload.get("transcript") or "").strip()
                        if transcript:
                            latest_transcript = transcript
                        await on_event(
                            {
                                "type": "transcript_update",
                                "event": event_name,
                                "transcript": transcript,
                                "confidence": payload.get("end_of_turn_confidence"),
                                "turn_index": payload.get("turn_index"),
                            }
                        )
                        if event_name == "EndOfTurn" and latest_transcript:
                            break
                        continue

                    if message_type in {"Warning", "Warnings"}:
                        logger.warning("Deepgram warning: %s", payload)
                        continue

                    if message_type in {"Error", "Err"}:
                        request_id = payload.get("request_id")
                        raise RuntimeError(
                            f"Deepgram Flux error{f' ({request_id})' if request_id else ''}: "
                            f"{payload.get('message') or payload}"
                        )
            finally:
                if not bridge_task.done():
                    bridge_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await bridge_task
                with contextlib.suppress(Exception):
                    await dg_ws.close()

        return latest_transcript.strip()

    async def _pipe_browser_to_deepgram(self, browser_ws: WebSocket, dg_ws: ClientConnection) -> None:
        while True:
            message = await browser_ws.receive()
            message_type = message.get("type")

            if message_type == "websocket.disconnect":
                await dg_ws.send(json.dumps({"type": "CloseStream"}))
                return

            if message_type != "websocket.receive":
                continue

            if message.get("bytes"):
                await dg_ws.send(message["bytes"])
                continue

            text = message.get("text")
            if not text:
                continue

            control = json.loads(text)
            if control.get("type") in {"finalize", "close", "CloseStream"}:
                await dg_ws.send(json.dumps({"type": "CloseStream"}))
                return

    async def transcribe_bytes(
        self,
        audio_bytes: bytes,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        headers = {"Authorization": f"Token {self.settings.deepgram_api_key}"}
        headers["Content-Type"] = content_type or "application/octet-stream"
        response = await self.http.post(
            "/v1/listen",
            params={"model": "nova-3", "smart_format": "true", "language": "en"},
            headers=headers,
            content=audio_bytes,
        )
        response.raise_for_status()
        data = response.json()
        request_id = data.get("metadata", {}).get("request_id") or response.headers.get("dg-request-id")
        if request_id:
            logger.info(
                "Deepgram prerecorded STT request_id=%s filename=%s bytes=%s",
                request_id,
                filename,
                len(audio_bytes),
            )
        channels = ((data.get("results") or {}).get("channels") or [])
        if not channels:
            return ""
        alternatives = channels[0].get("alternatives") or []
        if not alternatives:
            return ""
        return (alternatives[0].get("transcript") or "").strip()

    async def synthesize(self, text: str, voice_model: str) -> tuple[bytes | None, str | None, str | None]:
        cleaned = self._truncate_text(text)
        if not cleaned:
            return None, None, None

        params = self._build_tts_params(voice_model)

        response = await self.http.post(
            "/v1/speak",
            params=params,
            json={"text": cleaned},
        )

        if response.status_code >= 400:
            body = response.text
            logger.error(
                "Deepgram TTS failed status=%s params=%s body=%s",
                response.status_code,
                params,
                body,
            )
            raise RuntimeError(
                f"Deepgram TTS failed: status={response.status_code} body={body}"
            )

        content_type = response.headers.get("content-type", "audio/mpeg")
        extension = self._infer_audio_extension(content_type, params.get("encoding"))
        request_id = response.headers.get("dg-request-id")
        if request_id:
            logger.info(
                "Deepgram TTS request_id=%s voice=%s chars=%s encoding=%s",
                request_id,
                voice_model,
                len(cleaned),
                params.get("encoding"),
            )
        return response.content, content_type, extension

    async def summarize(self, text: str) -> str:
        response = await self.http.post(
            "/v1/read",
            params={"language": "en", "summarize": "true"},
            json={"text": text},
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or {}
        summary = results.get("summary") or {}
        summary_text = (summary.get("text") or summary.get("short") or "").strip()
        return summary_text or "No summary available."

    async def detect_topics(self, text: str) -> list[TopicHit]:
        response = await self.http.post(
            "/v1/read",
            params={"language": "en", "topics": "true"},
            json={"text": text},
        )
        response.raise_for_status()
        data = response.json()
        segments = (((data.get("results") or {}).get("topics") or {}).get("segments") or [])
        merged: dict[str, TopicHit] = {}
        for segment in segments:
            segment_text = (segment.get("text") or "").strip()
            for topic_entry in segment.get("topics") or []:
                topic_name = (topic_entry.get("topic") or "").strip()
                if not topic_name:
                    continue
                confidence = float(topic_entry.get("confidence_score") or 0.0)
                existing = merged.get(topic_name)
                if existing is None or confidence > existing.confidence_score:
                    merged[topic_name] = TopicHit(
                        topic=topic_name,
                        confidence_score=confidence,
                        source_text=segment_text,
                    )
        topics = sorted(merged.values(), key=lambda item: item.confidence_score, reverse=True)
        return topics[:8]

    def _build_tts_params(self, voice_model: str) -> dict[str, str]:
        encoding = (self.settings.tts_encoding or "mp3").lower()
        params: dict[str, str] = {
            "model": voice_model,
            "encoding": encoding,
        }

        # Deepgram TTS:
        # - mp3/flac/aac: no container parameter
        # - linear16/mulaw/alaw: container can be wav
        # - opus: container commonly ogg
        if encoding == "mp3":
            params["bit_rate"] = "48000"
        elif encoding in {"linear16", "mulaw", "alaw"}:
            container = getattr(self.settings, "tts_container", None)
            if container:
                params["container"] = container
            else:
                params["container"] = "wav"
        elif encoding == "opus":
            container = getattr(self.settings, "tts_container", None)
            params["container"] = container or "ogg"
        else:
            # For encodings like flac/aac, only include container if explicitly set and meaningful.
            container = getattr(self.settings, "tts_container", None)
            if container and container.lower() not in {"mp3", encoding}:
                params["container"] = container

        return params

    def _infer_audio_extension(self, content_type: str | None, encoding: str | None) -> str:
        lowered = (content_type or "").lower()
        encoding = (encoding or "").lower()

        if "mpeg" in lowered or encoding == "mp3":
            return "mp3"
        if "wav" in lowered or "wave" in lowered or encoding in {"linear16", "mulaw", "alaw"}:
            return "wav"
        if "ogg" in lowered or encoding == "opus":
            return "ogg"
        if "flac" in lowered or encoding == "flac":
            return "flac"
        if "aac" in lowered or encoding == "aac":
            return "aac"
        return "bin"

    def _truncate_text(self, text: str) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= self.settings.tts_max_chars:
            return cleaned
        truncated = cleaned[: self.settings.tts_max_chars]
        last_break = max(
            truncated.rfind("."),
            truncated.rfind("!"),
            truncated.rfind("?"),
            truncated.rfind(","),
        )
        if last_break > 120:
            truncated = truncated[: last_break + 1]
        return truncated.strip()