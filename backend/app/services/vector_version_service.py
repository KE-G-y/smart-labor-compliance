"""Vector collection version management helpers."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Tenant, VectorCollectionVersion
from app.security import sanitize_text
from app.services.runtime_config import set_db_config_value


ACTIVE_STATUS = "active"
BUILDING_STATUS = "building"
FAILED_STATUS = "failed"
READY_STATUS = "ready"
ARCHIVED_STATUS = "archived"


def manifest_sha256(path: Path) -> str:
    """计算 manifest 哈希，用于判断本次构建资料是否和上次一致。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_version_name(raw: Optional[str]) -> str:
    text = sanitize_text(raw) or datetime.utcnow().strftime("v%Y%m%d%H%M%S")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip(".-")
    return text[:80] or datetime.utcnow().strftime("v%Y%m%d%H%M%S")


def collection_name_for_version(base_collection: str, tenant: Tenant, version: str) -> str:
    """生成版本化 collection 名称。

    一个版本对应一个 Milvus collection，回滚时只需要切换激活 collection，
    不必覆盖或删除历史向量数据。
    """
    tenant_part = re.sub(r"[^A-Za-z0-9_]+", "_", tenant.code).strip("_") or f"tenant_{tenant.id}"
    version_part = re.sub(r"[^A-Za-z0-9_]+", "_", version).strip("_") or datetime.utcnow().strftime("v%Y%m%d%H%M%S")
    base_part = re.sub(r"[^A-Za-z0-9_]+", "_", base_collection).strip("_") or "slc_compliance_docs"
    return f"{base_part}_{tenant_part}_{version_part}"[:120]


def base_collection_name(configured_collection: str, tenant: Tenant) -> str:
    """Return the non-versioned collection prefix used for future builds."""
    configured = configured_collection or "slc_compliance_docs"
    tenant_part = re.sub(r"[^A-Za-z0-9_]+", "_", tenant.code).strip("_") or f"tenant_{tenant.id}"
    suffix = f"_{tenant_part}_"
    if suffix in configured:
        return configured.split(suffix, 1)[0] or "slc_compliance_docs"
    return configured


def create_or_replace_building_version(
    db: Session,
    *,
    tenant: Tenant,
    version: str,
    collection_name: str,
    manifest_path: str,
    manifest_hash: str,
    categories: list[str],
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    created_by: str,
    description: str = "",
) -> VectorCollectionVersion:
    """创建或重置一条 building 状态的版本记录。

    构建脚本开始写 Milvus 前先写 MySQL 记录，后续成功、失败、激活都更新这条记录。
    """
    existing = (
        db.query(VectorCollectionVersion)
        .filter(VectorCollectionVersion.tenant_id == tenant.id, VectorCollectionVersion.version == version)
        .first()
    )
    payload = {
        "collection_name": collection_name,
        "display_name": version,
        "description": sanitize_text(description),
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_hash,
        "categories": categories,
        "embedding_model": embedding_model,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "document_count": 0,
        "indexed_count": 0,
        "failed_count": 0,
        "chunk_count": 0,
        "status": BUILDING_STATUS,
        "is_active": False,
        "build_summary": None,
        "build_started_at": datetime.utcnow(),
        "build_finished_at": None,
        "activated_at": None,
        "activated_by": None,
        "created_by": created_by,
    }
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        return existing

    version_record = VectorCollectionVersion(tenant_id=tenant.id, version=version, **payload)
    db.add(version_record)
    db.flush()
    return version_record


def finish_version_build(
    db: Session,
    version_record: VectorCollectionVersion,
    *,
    document_count: int,
    indexed_count: int,
    failed_count: int,
    chunk_count: int,
    summary: dict,
) -> None:
    """构建完成后写入文档数、chunk 数和最终状态。"""
    version_record.document_count = document_count
    version_record.indexed_count = indexed_count
    version_record.failed_count = failed_count
    version_record.chunk_count = chunk_count
    version_record.build_summary = summary
    version_record.status = FAILED_STATUS if failed_count else READY_STATUS
    version_record.build_finished_at = datetime.utcnow()


def fail_version_build(db: Session, version_record: VectorCollectionVersion, *, error: str, summary: Optional[dict] = None) -> None:
    if summary:
        version_record.document_count = int(summary.get("total") or version_record.document_count or 0)
        version_record.indexed_count = int(summary.get("indexed") or version_record.indexed_count or 0)
        version_record.failed_count = max(int(summary.get("failed") or 0), 1)
        version_record.chunk_count = int(summary.get("chunks") or version_record.chunk_count or 0)
    else:
        version_record.failed_count = max(version_record.failed_count or 0, 1)
    version_record.status = FAILED_STATUS
    version_record.build_summary = {
        **(summary or {}),
        "error": sanitize_text(error) or error[:1000],
    }
    version_record.build_finished_at = datetime.utcnow()


def activate_version(db: Session, version_record: VectorCollectionVersion, *, activated_by: str = "system") -> None:
    """激活某个向量版本。

    激活会做两件事：
    1. 把同租户其他版本取消 active。
    2. 把系统配置 milvus_collection 切到该版本 collection。
    """
    active_versions = (
        db.query(VectorCollectionVersion)
        .filter(VectorCollectionVersion.tenant_id == version_record.tenant_id, VectorCollectionVersion.id != version_record.id)
        .filter(VectorCollectionVersion.is_active.is_(True))
        .all()
    )
    for item in active_versions:
        item.is_active = False
        if item.status == ACTIVE_STATUS:
            item.status = READY_STATUS
    version_record.is_active = True
    version_record.status = ACTIVE_STATUS
    version_record.activated_at = datetime.utcnow()
    version_record.activated_by = activated_by
    set_db_config_value(db, "milvus_collection", version_record.collection_name)
    set_db_config_value(db, "active_vector_version_id", str(version_record.id))


def archive_version(db: Session, version_record: VectorCollectionVersion) -> None:
    if version_record.is_active:
        raise ValueError("当前激活版本不能归档")
    version_record.status = ARCHIVED_STATUS
