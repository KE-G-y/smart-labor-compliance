"""
数据库与运行配置。

项目使用本机 Docker MySQL。为避免旧版演示表结构影响新项目，新的业务表统一使用
`slc_` 前缀。
"""
import json
from functools import lru_cache
from typing import Annotated, List
from urllib.parse import quote_plus

import pymysql
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


class Settings(BaseSettings):
    """应用配置，支持通过 backend/.env 覆盖。"""

    app_name: str = "企业用工与社保合规智能平台"
    app_env: str = "development"
    api_prefix: str = "/api"

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = "infini_rag_flow"
    db_name: str = "employment"

    jwt_secret_key: str = "change-this-dev-secret-before-production"
    jwt_expire_minutes: int = 480
    password_min_length: int = 8

    initial_admin_username: str = "admin"
    initial_admin_password: str = "Admin@123456"
    default_tenant_code: str = "demo-sx"

    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    max_request_bytes: int = 1024 * 1024
    max_upload_bytes: int = 10 * 1024 * 1024
    upload_dir: str = "storage/uploads"
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 120

    dify_base_url: str = "http://127.0.0.1/v1"
    dify_api_key: str = ""
    dify_timeout_seconds: int = 30

    langchain_base_url: str = ""
    langchain_api_key: str = ""
    langchain_model: str = ""
    langchain_embedding_model: str = "bge-m3"
    langchain_temperature: float = 0.2
    langchain_timeout_seconds: int = 45
    langsmith_tracing_enabled: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project: str = "smart-labor-compliance"

    milvus_uri: str = "http://127.0.0.1:19530"
    milvus_token: str = ""
    milvus_collection: str = "slc_compliance_docs"
    vector_search_mode: str = "hybrid"
    vector_top_k: int = 4
    vector_chunk_size: int = 500
    vector_chunk_overlap: int = 50
    local_embedding_enabled: bool = True
    local_embedding_model_path: str = "models/bge-m3"
    local_reranker_enabled: bool = True
    local_reranker_model_path: str = "models/bge-reranker-large"
    local_fallback_bert_model_path: str = "models/bert-base-chinese"

    ragflow_base_url: str = "http://127.0.0.1:9380"
    ragflow_web_url: str = "http://127.0.0.1:8880"
    ragflow_api_key: str = ""
    ragflow_timeout_seconds: int = 10

    auto_seed: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def _safe_identifier(identifier: str) -> str:
    return identifier.replace("`", "``")


def create_database_if_not_exists() -> None:
    """确保目标库存在。"""
    connection = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{_safe_identifier(settings.db_name)}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        connection.commit()
    finally:
        connection.close()


DATABASE_URL = (
    f"mysql+pymysql://{quote_plus(settings.db_user)}:{quote_plus(settings.db_password)}"
    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}?charset=utf8mb4"
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：获取数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """初始化表结构与演示数据。"""
    create_database_if_not_exists()

    from app.models import (
        admin,
        chat_log,
        feedback,
        knowledge_package,
        source,
        tenant,
        test_question,
        vector_version,
    )

    Base.metadata.create_all(bind=engine)
    ensure_compat_columns()

    if settings.auto_seed:
        from app.services.seed_data import seed_initial_data

        with SessionLocal() as db:
            seed_initial_data(db)


def ensure_compat_columns() -> None:
    """为已存在的旧演示库补齐新增字段。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    def add_missing_columns(table_name: str, definitions: dict[str, str]) -> None:
        if table_name not in tables:
            return
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        with engine.begin() as connection:
            for column_name, ddl in definitions.items():
                if column_name not in columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))

    def add_missing_indexes(table_name: str, definitions: dict[str, str]) -> None:
        if table_name not in tables:
            return
        indexes = {
            index["name"]
            for index in inspector.get_indexes(table_name)
        } | {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table_name)
            if constraint.get("name")
        }
        with engine.begin() as connection:
            for index_name, ddl in definitions.items():
                if index_name not in indexes:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD INDEX {index_name} {ddl}"))

    def add_missing_unique_indexes(table_name: str, definitions: dict[str, str]) -> None:
        if table_name not in tables:
            return
        indexes = {
            index["name"]
            for index in inspector.get_indexes(table_name)
        } | {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table_name)
            if constraint.get("name")
        }
        with engine.begin() as connection:
            for index_name, ddl in definitions.items():
                if index_name not in indexes:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD UNIQUE KEY {index_name} {ddl}"))

    add_missing_columns(
        "slc_sources",
        {
            "source_code": "source_code VARCHAR(40) NULL AFTER tenant_id",
            "reviewed_at": "reviewed_at DATETIME NULL AFTER review_status",
            "reviewed_by": "reviewed_by VARCHAR(80) NULL AFTER reviewed_at",
            "captured_at": "captured_at DATE NULL AFTER review_status",
            "owner": "owner VARCHAR(80) NULL AFTER captured_at",
            "local_file": "local_file VARCHAR(500) NULL AFTER owner",
            "note": "note TEXT NULL AFTER local_file",
        },
    )
    if "slc_sources" in tables:
        with engine.begin() as connection:
            connection.execute(text("UPDATE slc_sources SET issuer = '' WHERE issuer IS NULL"))
            connection.execute(text("""
                UPDATE slc_sources
                SET reviewed_at = COALESCE(reviewed_at, created_at),
                    reviewed_by = COALESCE(reviewed_by, owner, '系统初始化')
                WHERE review_status IN ('已复核', 'reviewed')
            """))
            connection.execute(text("ALTER TABLE slc_sources MODIFY issuer VARCHAR(120) NOT NULL DEFAULT ''"))
    add_missing_indexes("slc_sources", {"ix_slc_sources_source_code": "(source_code)"})
    add_missing_columns("slc_chat_logs", {"evaluation": "evaluation JSON NULL AFTER risk_level"})
    add_missing_columns(
        "slc_vector_collection_versions",
        {
            "display_name": "display_name VARCHAR(160) NULL AFTER collection_name",
            "description": "description TEXT NULL AFTER display_name",
            "manifest_path": "manifest_path VARCHAR(500) NULL AFTER description",
            "manifest_sha256": "manifest_sha256 VARCHAR(64) NULL AFTER manifest_path",
            "categories": "categories JSON NULL AFTER manifest_sha256",
            "embedding_model": "embedding_model VARCHAR(120) NULL AFTER categories",
            "chunk_size": "chunk_size INT NULL AFTER embedding_model",
            "chunk_overlap": "chunk_overlap INT NULL AFTER chunk_size",
            "document_count": "document_count INT NOT NULL DEFAULT 0 AFTER chunk_overlap",
            "indexed_count": "indexed_count INT NOT NULL DEFAULT 0 AFTER document_count",
            "failed_count": "failed_count INT NOT NULL DEFAULT 0 AFTER indexed_count",
            "chunk_count": "chunk_count INT NOT NULL DEFAULT 0 AFTER failed_count",
            "status": "status VARCHAR(30) NOT NULL DEFAULT 'building' AFTER chunk_count",
            "is_active": "is_active TINYINT(1) NOT NULL DEFAULT 0 AFTER status",
            "build_summary": "build_summary JSON NULL AFTER is_active",
            "build_started_at": "build_started_at DATETIME NULL AFTER build_summary",
            "build_finished_at": "build_finished_at DATETIME NULL AFTER build_started_at",
            "activated_at": "activated_at DATETIME NULL AFTER build_finished_at",
            "activated_by": "activated_by VARCHAR(80) NULL AFTER activated_at",
            "created_by": "created_by VARCHAR(80) NULL AFTER activated_by",
            "created_at": "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER created_by",
            "updated_at": "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at",
        },
    )
    add_missing_indexes(
        "slc_vector_collection_versions",
        {
            "ix_slc_vector_collection_versions_tenant_id": "(tenant_id)",
            "ix_slc_vector_collection_versions_collection_name": "(collection_name)",
            "ix_slc_vector_collection_versions_status": "(status)",
            "ix_slc_vector_collection_versions_is_active": "(is_active)",
        },
    )
    deduplicate_business_data()
    add_missing_unique_indexes(
        "slc_sources",
        {
            "uq_slc_sources_tenant_source_code": "(tenant_id, source_code)",
            "uq_slc_sources_tenant_url": "(tenant_id, url)",
            "uq_slc_sources_tenant_title_issuer": "(tenant_id, title, issuer)",
        },
    )
    add_missing_unique_indexes(
        "slc_vector_collection_versions",
        {
            "uq_slc_vector_versions_tenant_version": "(tenant_id, version)",
            "uq_slc_vector_versions_tenant_collection": "(tenant_id, collection_name)",
        },
    )


def deduplicate_business_data() -> None:
    """清理历史重复来源，只保留每组最早记录。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "slc_sources" not in tables:
        return

    def resolved_source_id(source_id: int, duplicate_map: dict[int, int]) -> int:
        current = source_id
        visited = set()
        while current in duplicate_map and current not in visited:
            visited.add(current)
            current = duplicate_map[current]
        return current

    with engine.begin() as connection:
        if "slc_sources" in tables:
            source_rows = connection.execute(text("""
                SELECT id, tenant_id, source_code, url, title, issuer
                FROM slc_sources
                ORDER BY id ASC
            """)).mappings().all()
            duplicate_map: dict[int, int] = {}
            for fields in (("tenant_id", "source_code"), ("tenant_id", "url"), ("tenant_id", "title", "issuer")):
                groups: dict[tuple, list[int]] = {}
                for row in source_rows:
                    key = tuple((row[field] or "").strip() if isinstance(row[field], str) else row[field] for field in fields)
                    if any(value in (None, "") for value in key):
                        continue
                    groups.setdefault(key, []).append(row["id"])
                for ids in groups.values():
                    if len(ids) < 2:
                        continue
                    keep_id = min(ids)
                    for source_id in ids:
                        if source_id != keep_id:
                            duplicate_map[source_id] = keep_id

            duplicate_map = {
                duplicate_id: resolved_source_id(keep_id, duplicate_map)
                for duplicate_id, keep_id in duplicate_map.items()
                if duplicate_id != resolved_source_id(keep_id, duplicate_map)
            }

            if duplicate_map:
                delete_ids = ",".join(str(source_id) for source_id in sorted(duplicate_map))
                connection.execute(text(f"DELETE FROM slc_sources WHERE id IN ({delete_ids})"))
