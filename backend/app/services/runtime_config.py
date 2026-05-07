"""Runtime configuration helpers shared by admin APIs and service calls."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.database import settings
from app.models import SystemConfig


CONFIG_KEYS = {
    "dify_base_url",
    "dify_api_key",
    "dify_timeout_seconds",
    "ragflow_base_url",
    "ragflow_web_url",
    "ragflow_api_key",
    "ragflow_timeout_seconds",
}

URL_CONFIG_KEYS = {"dify_base_url", "ragflow_base_url", "ragflow_web_url"}
SECRET_CONFIG_KEYS = {"dify_api_key", "ragflow_api_key"}
TIMEOUT_CONFIG_LIMITS = {
    "dify_timeout_seconds": (5, 300),
    "ragflow_timeout_seconds": (5, 120),
}


@dataclass(frozen=True)
class RuntimeConfig:
    dify_base_url: str
    dify_api_key: str
    dify_timeout_seconds: int
    ragflow_base_url: str
    ragflow_web_url: str
    ragflow_api_key: str
    ragflow_timeout_seconds: int


def _clean_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_url(key: str, value: object) -> Optional[str]:
    text = _clean_text(value)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{key} 必须是完整的 http(s) 地址")
    return text.rstrip("/")


def _normalize_timeout(key: str, value: object) -> Optional[str]:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        seconds = int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} 必须是整数秒数") from exc
    minimum, maximum = TIMEOUT_CONFIG_LIMITS[key]
    if seconds < minimum or seconds > maximum:
        raise ValueError(f"{key} 必须在 {minimum}-{maximum} 秒之间")
    return str(seconds)


def normalize_config_update(key: str, value: object) -> Optional[str]:
    if key not in CONFIG_KEYS:
        return None
    if key in URL_CONFIG_KEYS:
        return _normalize_url(key, value)
    if key in TIMEOUT_CONFIG_LIMITS:
        return _normalize_timeout(key, value)
    if key in SECRET_CONFIG_KEYS:
        return _clean_text(value)
    return _clean_text(value)


def get_db_config_value(db: Session, key: str) -> Optional[str]:
    row = db.query(SystemConfig).filter(SystemConfig.id == key).first()
    return row.value if row else None


def set_db_config_value(db: Session, key: str, value: Optional[str]) -> None:
    existing = db.query(SystemConfig).filter(SystemConfig.id == key).first()
    if existing:
        existing.value = value
    else:
        db.add(SystemConfig(id=key, value=value))


def _db_config_map(db: Session) -> dict[str, Optional[str]]:
    rows = db.query(SystemConfig).filter(SystemConfig.id.in_(CONFIG_KEYS)).all()
    return {row.id: row.value for row in rows}


def _effective_text(raw: dict[str, Optional[str]], key: str, default: str) -> str:
    return _clean_text(raw.get(key)) or str(default or "")


def _effective_timeout(raw: dict[str, Optional[str]], key: str, default: int) -> int:
    value = _clean_text(raw.get(key))
    if value is None:
        return default
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return default
    minimum, maximum = TIMEOUT_CONFIG_LIMITS[key]
    return max(minimum, min(maximum, seconds))


def get_runtime_config(db: Session) -> RuntimeConfig:
    raw = _db_config_map(db)
    return RuntimeConfig(
        dify_base_url=_effective_text(raw, "dify_base_url", settings.dify_base_url),
        dify_api_key=_effective_text(raw, "dify_api_key", settings.dify_api_key),
        dify_timeout_seconds=_effective_timeout(raw, "dify_timeout_seconds", settings.dify_timeout_seconds),
        ragflow_base_url=_effective_text(raw, "ragflow_base_url", settings.ragflow_base_url),
        ragflow_web_url=_effective_text(raw, "ragflow_web_url", settings.ragflow_web_url),
        ragflow_api_key=_effective_text(raw, "ragflow_api_key", settings.ragflow_api_key),
        ragflow_timeout_seconds=_effective_timeout(raw, "ragflow_timeout_seconds", settings.ragflow_timeout_seconds),
    )
