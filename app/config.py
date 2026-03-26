from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Atlas Lingua", alias="APP_NAME")
    app_tagline: str = Field(default="Deepgram + OpenAI language tutor demo", alias="APP_TAGLINE")
    app_env: str = Field(default="development", alias="APP_ENV")

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    deepgram_api_key: str = Field(default="", alias="DEEPGRAM_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.4-mini", alias="OPENAI_MODEL")

    force_mock_mode: bool = Field(default=False, alias="MOCK_MODE")
    media_root: Path = Field(default=PROJECT_ROOT / "runtime_media", alias="MEDIA_ROOT")

    flux_model: str = Field(default="flux-general-en", alias="FLUX_MODEL")
    flux_eot_threshold: float = Field(default=0.8, alias="FLUX_EOT_THRESHOLD")
    flux_eot_timeout_ms: int = Field(default=6000, alias="FLUX_EOT_TIMEOUT_MS")
    flux_eager_eot_threshold: float | None = Field(default=None, alias="FLUX_EAGER_EOT_THRESHOLD")

    tts_max_chars: int = Field(default=1800, alias="TTS_MAX_CHARS")
    tts_encoding: str = Field(default="mp3", alias="TTS_ENCODING")
    tts_container: str = Field(default="mp3", alias="TTS_CONTAINER")

    ui_title: str = Field(default="Atlas Lingua", alias="UI_TITLE")


    @field_validator("flux_eager_eot_threshold", mode="before")
    @classmethod
    def _empty_eager_threshold_to_none(cls, value):
        if value in ("", None):
            return None
        return value

    @property
    def effective_mock_mode(self) -> bool:
        if self.force_mock_mode:
            return True
        return not (self.deepgram_api_key and self.openai_api_key)

    @property
    def media_root_resolved(self) -> Path:
        self.media_root.mkdir(parents=True, exist_ok=True)
        return self.media_root


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
