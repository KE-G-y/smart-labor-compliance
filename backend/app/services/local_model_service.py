"""Optional local AI model adapters.

The files under backend/models are large offline models. This module loads them
only when a feature asks for them, so the basic FastAPI app can still run without
torch/transformers installed.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from app.database import settings
from app.security import sanitize_text


logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_DIR = BACKEND_DIR / "models"


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _model_path(configured_path: str, fallback_name: str) -> Path:
    raw = (configured_path or "").strip()
    if raw:
        path = Path(raw).expanduser()
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()
    return DEFAULT_MODELS_DIR / fallback_name


def local_embedding_enabled(config: Any = None) -> bool:
    value = getattr(config, "local_embedding_enabled", settings.local_embedding_enabled)
    return _truthy(value)


def local_reranker_enabled(config: Any = None) -> bool:
    value = getattr(config, "local_reranker_enabled", settings.local_reranker_enabled)
    return _truthy(value)


def local_embedding_model_path(config: Any = None) -> Path:
    return _model_path(
        getattr(config, "local_embedding_model_path", settings.local_embedding_model_path),
        "bge-m3",
    )


def local_reranker_model_path(config: Any = None) -> Path:
    return _model_path(
        getattr(config, "local_reranker_model_path", settings.local_reranker_model_path),
        "bge-reranker-large",
    )

def local_fallback_bert_model_path(config: Any = None) -> Path:
    return _model_path(
        getattr(config, "local_fallback_bert_model_path", settings.local_fallback_bert_model_path),
        "bert-base-chinese",
    )


class LocalSentenceTransformerEmbeddings:
    """LangChain-compatible embeddings backed by backend/models/bge-m3."""

    def __init__(self, model_path: Path, *, batch_size: int = 16):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("本地 Embedding 依赖 sentence-transformers/torch 未安装") from exc

        if not model_path.exists():
            raise RuntimeError(f"本地 Embedding 模型目录不存在：{model_path}")
        self.model_path = model_path
        self.batch_size = batch_size
        self.model = SentenceTransformer(str(model_path), device=os.getenv("LOCAL_MODEL_DEVICE") or None)

    def _encode(self, texts: Iterable[str]) -> list[list[float]]:
        cleaned = [sanitize_text(text) or "" for text in texts]
        vectors = self.model.encode(
            cleaned,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]


@lru_cache(maxsize=4)
def get_local_embeddings(model_path: str) -> LocalSentenceTransformerEmbeddings:
    return LocalSentenceTransformerEmbeddings(Path(model_path))


class LocalReranker:
    """Cross-encoder reranker backed by backend/models/bge-reranker-large."""

    def __init__(self, model_path: Path):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError("本地重排依赖 sentence-transformers/torch 未安装") from exc
        if not model_path.exists():
            raise RuntimeError(f"本地重排模型目录不存在：{model_path}")
        self.model_path = model_path
        self.model = CrossEncoder(str(model_path), device=os.getenv("LOCAL_MODEL_DEVICE") or None)

    def rerank(self, query: str, documents: list[Any], *, top_k: int) -> list[Any]:
        if len(documents) <= 1:
            return documents[:top_k]
        pairs = [(query, getattr(document, "page_content", "") or "") for document in documents]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(documents, scores), key=lambda item: float(item[1]), reverse=True)
        return [document for document, _score in ranked[:top_k]]


@lru_cache(maxsize=4)
def get_local_reranker(model_path: str) -> LocalReranker:
    return LocalReranker(Path(model_path))


def local_model_status(config: Any = None) -> dict[str, Any]:
    """Return lightweight status without loading model weights."""
    paths = {
        "embedding": local_embedding_model_path(config),
        "reranker": local_reranker_model_path(config),
        "fallback_bert": local_fallback_bert_model_path(config),
    }
    return {
        "models_dir": str(DEFAULT_MODELS_DIR),
        "embedding": {
            "enabled": local_embedding_enabled(config),
            "path": str(paths["embedding"]),
            "exists": paths["embedding"].exists(),
        },
        "reranker": {
            "enabled": local_reranker_enabled(config),
            "path": str(paths["reranker"]),
            "exists": paths["reranker"].exists(),
        },
        "fallback_bert": {
            "path": str(paths["fallback_bert"]),
            "exists": paths["fallback_bert"].exists(),
        },
    }
