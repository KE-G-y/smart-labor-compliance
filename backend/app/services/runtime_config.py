"""Runtime configuration helpers shared by admin APIs and service calls."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.database import settings
from app.models import SystemConfig


CONFIG_KEYS = {
    "query_strategy",
    "dify_base_url",
    "dify_api_key",
    "dify_timeout_seconds",
    "langchain_base_url",
    "langchain_api_key",
    "langchain_model",
    "langchain_embedding_model",
    "langchain_temperature",
    "langchain_timeout_seconds",
    "langsmith_tracing_enabled",
    "langsmith_endpoint",
    "langsmith_api_key",
    "langsmith_project",
    "milvus_uri",
    "milvus_token",
    "milvus_collection",
    "active_vector_version_id",
    "vector_search_mode",
    "vector_top_k",
    "vector_chunk_size",
    "vector_chunk_overlap",
    "local_embedding_enabled",
    "local_embedding_model_path",
    "local_reranker_enabled",
    "local_reranker_model_path",
    "local_fallback_bert_model_path",
    "ragflow_base_url",
    "ragflow_web_url",
    "ragflow_api_key",
    "ragflow_timeout_seconds",
}

URL_CONFIG_KEYS = {"dify_base_url", "langchain_base_url", "langsmith_endpoint", "ragflow_base_url", "ragflow_web_url"}
SECRET_CONFIG_KEYS = {"dify_api_key", "langchain_api_key", "langsmith_api_key", "milvus_token", "ragflow_api_key"}
TIMEOUT_CONFIG_LIMITS = {
    "dify_timeout_seconds": (5, 300),
    "langchain_timeout_seconds": (5, 300),
    "ragflow_timeout_seconds": (5, 120),
}
INTEGER_CONFIG_LIMITS = {
    "vector_top_k": (1, 12),
    "vector_chunk_size": (300, 5000),
    "vector_chunk_overlap": (0, 1000),
}
BOOLEAN_CONFIG_KEYS = {
    "local_embedding_enabled",
    "local_reranker_enabled",
    "langsmith_tracing_enabled",
}
TEMPERATURE_CONFIG_LIMITS = {
    "langchain_temperature": (0.0, 2.0),
}
DEFAULT_QUERY_STRATEGY = "langchain_first"
VECTOR_SEARCH_MODES = {"dense", "hybrid"}
QUERY_STRATEGIES = {
    "langchain_first",
    "dify_first",
    "langchain_only",
    "dify_only",
    "vector_only",
}


@dataclass(frozen=True)
class RuntimeConfig:
    """运行时配置快照。

    每次问答或入库时读取一次，避免服务启动后改了后台配置却不生效。
    """

    query_strategy: str
    dify_base_url: str
    dify_api_key: str
    dify_timeout_seconds: int
    langchain_base_url: str
    langchain_api_key: str
    langchain_model: str
    langchain_embedding_model: str
    langchain_temperature: float
    langchain_timeout_seconds: int
    langsmith_tracing_enabled: bool
    langsmith_endpoint: str
    langsmith_api_key: str
    langsmith_project: str
    milvus_uri: str
    milvus_token: str
    milvus_collection: str
    active_vector_version_id: str
    vector_search_mode: str
    vector_top_k: int
    vector_chunk_size: int
    vector_chunk_overlap: int
    local_embedding_enabled: bool
    local_embedding_model_path: str
    local_reranker_enabled: bool
    local_reranker_model_path: str
    local_fallback_bert_model_path: str
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


def _normalize_integer(key: str, value: object) -> Optional[str]:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        number = int(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} 必须是整数") from exc
    minimum, maximum = INTEGER_CONFIG_LIMITS[key]
    if number < minimum or number > maximum:
        raise ValueError(f"{key} 必须在 {minimum}-{maximum} 之间")
    return str(number)


def _normalize_temperature(key: str, value: object) -> Optional[str]:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        temperature = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} 必须是数字") from exc
    minimum, maximum = TEMPERATURE_CONFIG_LIMITS[key]
    if temperature < minimum or temperature > maximum:
        raise ValueError(f"{key} 必须在 {minimum}-{maximum} 之间")
    return str(temperature)


def _normalize_boolean(key: str, value: object) -> Optional[str]:
    text = _clean_text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return "true"
    if lowered in {"0", "false", "no", "off"}:
        return "false"
    raise ValueError(f"{key} 必须是 true 或 false")


def _normalize_query_strategy(value: object) -> str:
    """校验管理员选择的查询方案。

    local_faq_only 是历史配置名，现在统一映射到 vector_only，避免旧库升级后失效。
    """
    text = _clean_text(value) or DEFAULT_QUERY_STRATEGY
    if text == "local_faq_only":
        text = "vector_only"
    if text not in QUERY_STRATEGIES:
        allowed = "、".join(sorted(QUERY_STRATEGIES))
        raise ValueError(f"query_strategy 必须是以下值之一：{allowed}")
    return text


def _normalize_vector_search_mode(value: object) -> str:
    text = (_clean_text(value) or "hybrid").lower()
    if text not in VECTOR_SEARCH_MODES:
        allowed = "、".join(sorted(VECTOR_SEARCH_MODES))
        raise ValueError(f"vector_search_mode 必须是以下值之一：{allowed}")
    return text


def normalize_config_update(key: str, value: object) -> Optional[str]:
    """保存配置前做白名单和类型校验。

    这样非法 URL、过大的 chunk_size、异常 temperature 不会写进数据库。
    """
    if key not in CONFIG_KEYS:
        return None
    if key == "query_strategy":
        return _normalize_query_strategy(value)
    if key == "vector_search_mode":
        return _normalize_vector_search_mode(value)
    if key in URL_CONFIG_KEYS:
        return _normalize_url(key, value)
    if key in TIMEOUT_CONFIG_LIMITS:
        return _normalize_timeout(key, value)
    if key in INTEGER_CONFIG_LIMITS:
        return _normalize_integer(key, value)
    if key in TEMPERATURE_CONFIG_LIMITS:
        return _normalize_temperature(key, value)
    if key in BOOLEAN_CONFIG_KEYS:
        return _normalize_boolean(key, value)
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


def _effective_integer(raw: dict[str, Optional[str]], key: str, default: int) -> int:
    value = _clean_text(raw.get(key))
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    minimum, maximum = INTEGER_CONFIG_LIMITS[key]
    return max(minimum, min(maximum, number))


def _effective_temperature(raw: dict[str, Optional[str]], key: str, default: float) -> float:
    value = _clean_text(raw.get(key))
    if value is None:
        return default
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return default
    minimum, maximum = TEMPERATURE_CONFIG_LIMITS[key]
    return max(minimum, min(maximum, temperature))


def _effective_boolean(raw: dict[str, Optional[str]], key: str, default: bool) -> bool:
    value = _clean_text(raw.get(key))
    if value is None:
        return bool(default)
    return value.lower() in {"1", "true", "yes", "on"}


def _effective_query_strategy(raw: dict[str, Optional[str]]) -> str:
    try:
        return _normalize_query_strategy(raw.get("query_strategy"))
    except ValueError:
        return DEFAULT_QUERY_STRATEGY


def _effective_vector_search_mode(raw: dict[str, Optional[str]]) -> str:
    try:
        return _normalize_vector_search_mode(raw.get("vector_search_mode") or settings.vector_search_mode)
    except ValueError:
        return "hybrid"


def get_runtime_config(db: Session) -> RuntimeConfig:
    """合并数据库配置和 .env 默认值。

    数据库配置来自管理后台，优先级更高；没有配置时回退到 settings。
    """
    raw = _db_config_map(db)
    return RuntimeConfig(
        query_strategy=_effective_query_strategy(raw),
        dify_base_url=_effective_text(raw, "dify_base_url", settings.dify_base_url),
        dify_api_key=_effective_text(raw, "dify_api_key", settings.dify_api_key),
        dify_timeout_seconds=_effective_timeout(raw, "dify_timeout_seconds", settings.dify_timeout_seconds),
        langchain_base_url=_effective_text(raw, "langchain_base_url", settings.langchain_base_url),
        langchain_api_key=_effective_text(raw, "langchain_api_key", settings.langchain_api_key),
        langchain_model=_effective_text(raw, "langchain_model", settings.langchain_model),
        langchain_embedding_model=_effective_text(
            raw,
            "langchain_embedding_model",
            settings.langchain_embedding_model,
        ),
        langchain_temperature=_effective_temperature(
            raw,
            "langchain_temperature",
            settings.langchain_temperature,
        ),
        langchain_timeout_seconds=_effective_timeout(
            raw,
            "langchain_timeout_seconds",
            settings.langchain_timeout_seconds,
        ),
        langsmith_tracing_enabled=_effective_boolean(
            raw,
            "langsmith_tracing_enabled",
            settings.langsmith_tracing_enabled,
        ),
        langsmith_endpoint=_effective_text(raw, "langsmith_endpoint", settings.langsmith_endpoint),
        langsmith_api_key=_effective_text(raw, "langsmith_api_key", settings.langsmith_api_key),
        langsmith_project=_effective_text(raw, "langsmith_project", settings.langsmith_project),
        milvus_uri=_effective_text(raw, "milvus_uri", settings.milvus_uri),
        milvus_token=_effective_text(raw, "milvus_token", settings.milvus_token),
        milvus_collection=_effective_text(raw, "milvus_collection", settings.milvus_collection),
        active_vector_version_id=_effective_text(raw, "active_vector_version_id", ""),
        vector_search_mode=_effective_vector_search_mode(raw),
        vector_top_k=_effective_integer(raw, "vector_top_k", settings.vector_top_k),
        vector_chunk_size=_effective_integer(raw, "vector_chunk_size", settings.vector_chunk_size),
        vector_chunk_overlap=_effective_integer(raw, "vector_chunk_overlap", settings.vector_chunk_overlap),
        local_embedding_enabled=_effective_boolean(raw, "local_embedding_enabled", settings.local_embedding_enabled),
        local_embedding_model_path=_effective_text(
            raw,
            "local_embedding_model_path",
            settings.local_embedding_model_path,
        ),
        local_reranker_enabled=_effective_boolean(raw, "local_reranker_enabled", settings.local_reranker_enabled),
        local_reranker_model_path=_effective_text(
            raw,
            "local_reranker_model_path",
            settings.local_reranker_model_path,
        ),
        local_fallback_bert_model_path=_effective_text(
            raw,
            "local_fallback_bert_model_path",
            settings.local_fallback_bert_model_path,
        ),
        ragflow_base_url=_effective_text(raw, "ragflow_base_url", settings.ragflow_base_url),
        ragflow_web_url=_effective_text(raw, "ragflow_web_url", settings.ragflow_web_url),
        ragflow_api_key=_effective_text(raw, "ragflow_api_key", settings.ragflow_api_key),
        ragflow_timeout_seconds=_effective_timeout(raw, "ragflow_timeout_seconds", settings.ragflow_timeout_seconds),
    )
