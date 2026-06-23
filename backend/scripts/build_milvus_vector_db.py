#!/usr/bin/env python3
"""Build the Milvus vector database from a prepared knowledge-base manifest.

小白版流程：
1. 读取 `manifest.csv`，知道有哪些 Markdown 资料需要入库。
2. 为本次构建生成一个新的 Milvus collection 名称。
3. 逐个文件解析、切分、Embedding，并写入 Milvus。
4. 在 MySQL 记录这个向量版本，成功后可自动激活。
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable, Iterable, Optional


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_KB_DIR = REPO_ROOT / "knowledge_base" / "langchain_vector_import"
DEFAULT_MANIFEST = DEFAULT_KB_DIR / "manifest.csv"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


logger = logging.getLogger("build_milvus_vector_db")


def display_path(path: Path) -> str:
    """把本机路径转换成项目内相对路径，避免摘要和页面暴露绝对路径。"""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


@dataclass(frozen=True)
class BuildItem:
    document_id: str
    title: str
    kb_category: str
    doc_type: str
    region: str
    issuer: str
    publish_date: str
    effective_date: str
    validity_status: str
    review_status: str
    source_ids: str
    url: str
    prepared_file: str
    source_relative_path: str
    sha256: str
    characters: int
    vector_priority: int
    notes: str


@dataclass
class BuildSummary:
    tenant_code: str
    manifest: str
    collection: str
    version: str
    dry_run: bool
    total: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    chunks: int = 0
    document_indexed: int = 0
    quality_reports: list[dict] | None = None
    quality_overview: dict | None = None
    quality_report_errors: list[dict[str, str]] | None = None
    errors: list[dict[str, str]] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Milvus vectors from prepared knowledge-base Markdown files.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to manifest.csv")
    parser.add_argument("--tenant-code", default="demo-sx", help="Tenant code for vector metadata")
    parser.add_argument(
        "--categories",
        default="",
        help="Comma-separated kb_category filter, for example: national_law,shaanxi_policy,xian_service_rule",
    )
    parser.add_argument("--limit", type=int, default=0, help="Only index the first N matched documents")
    parser.add_argument("--include-manifest-faqs", action="store_true", default=True, help="Index standard_faq files from manifest.csv")
    parser.add_argument("--dry-run", action="store_true", help="Print build plan without writing to Milvus")
    parser.add_argument("--reset-collection", action="store_true", help="Drop the target Milvus collection before indexing")
    parser.add_argument("--version", default="", help="Vector collection version name, defaults to a timestamp")
    parser.add_argument("--base-collection", default=os.getenv("MILVUS_BASE_COLLECTION", ""), help="Base Milvus collection prefix used to generate versioned collection names")
    parser.add_argument("--collection-name", default="", help="Milvus collection name for this version")
    parser.add_argument("--description", default="", help="Version description")
    parser.add_argument("--activate", action=argparse.BooleanOptionalAction, default=True, help="Activate this version after a successful build")
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero status if any document fails")
    parser.add_argument("--summary-file", default="", help="Optional JSON summary output path")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def load_manifest(path: Path, categories: set[str]) -> list[BuildItem]:
    """读取知识库 manifest，并按优先级排序。

    vector_priority 越高越先入库，方便官方来源优先、FAQ 次之。
    """
    if not path.exists():
        raise SystemExit(f"manifest not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    items = []
    for row in rows:
        item = BuildItem(
            document_id=row.get("document_id", "").strip(),
            title=row.get("title", "").strip(),
            kb_category=row.get("kb_category", "").strip(),
            doc_type=row.get("doc_type", "").strip(),
            region=row.get("region", "").strip(),
            issuer=row.get("issuer", "").strip(),
            publish_date=row.get("publish_date", "").strip(),
            effective_date=row.get("effective_date", "").strip(),
            validity_status=row.get("validity_status", "").strip(),
            review_status=row.get("review_status", "").strip(),
            source_ids=row.get("source_ids", "").strip(),
            url=row.get("url", "").strip(),
            prepared_file=row.get("prepared_file", "").strip(),
            source_relative_path=row.get("source_relative_path", "").strip(),
            sha256=row.get("sha256", "").strip(),
            characters=int(row.get("characters") or 0),
            vector_priority=int(row.get("vector_priority") or 0),
            notes=row.get("notes", "").strip(),
        )
        if categories and item.kb_category not in categories:
            continue
        items.append(item)
    return sorted(items, key=lambda item: (-item.vector_priority, item.document_id))


def filter_manifest_items(items: list[BuildItem], *, include_manifest_faqs: bool) -> list[BuildItem]:
    if include_manifest_faqs:
        return items
    return [item for item in items if item.kb_category != "standard_faq" and item.doc_type != "FAQ标准问答"]


def resolve_document_path(manifest_path: Path, prepared_file: str) -> Path:
    candidate = manifest_path.parent / prepared_file
    if not candidate.exists():
        raise FileNotFoundError(f"prepared file not found: {candidate}")
    return candidate


def source_code_candidates(item: BuildItem) -> list[str]:
    raw_codes = []
    for value in (item.document_id, item.source_ids):
        raw_codes.extend(value.replace(";", ",").split(","))
    candidates = []
    for code in raw_codes:
        code = code.strip()
        if code and code not in candidates:
            candidates.append(code)
    return candidates


def find_source_id(db, source_model, tenant_id: int, item: BuildItem) -> Optional[int]:
    candidates = source_code_candidates(item)
    if not candidates:
        return None
    source = (
        db.query(source_model)
        .filter(source_model.tenant_id == tenant_id, source_model.source_code.in_(candidates))
        .order_by(source_model.id.asc())
        .first()
    )
    return source.id if source else None


def extra_metadata(item: BuildItem) -> dict:
    """把 manifest 字段转成 Milvus metadata。

    这些字段不会参与向量计算，但会随检索结果返回，用于展示地区、
    发布机构、来源编号、FAQ 分类等信息。
    """
    return {
        "kb_category": item.kb_category,
        "doc_type": item.doc_type,
        "region": item.region,
        "issuer": item.issuer,
        "publish_date": item.publish_date,
        "effective_date": item.effective_date,
        "validity_status": item.validity_status,
        "review_status": item.review_status,
        "source_ids": item.source_ids,
        "url": item.url,
        "source_relative_path": item.source_relative_path,
        "sha256": item.sha256,
        "vector_priority": item.vector_priority,
        "notes": item.notes,
        "builder": "backend/scripts/build_milvus_vector_db.py",
    }


def refresh_quality_overview(summary: BuildSummary) -> None:
    """根据每份文档的质量报告，汇总出版本级质量概览。"""
    reports = summary.quality_reports or []
    scores = [int(report.get("score") or 0) for report in reports]
    status_counts: dict[str, int] = {"pass": 0, "warning": 0, "fail": 0}
    for report in reports:
        status = str(report.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    summary.quality_overview = {
        "total_reports": len(reports),
        "average_score": round(sum(scores) / len(scores)) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "pass_count": status_counts.get("pass", 0),
        "warning_count": status_counts.get("warning", 0),
        "fail_count": status_counts.get("fail", 0),
        "needs_review_count": status_counts.get("warning", 0) + status_counts.get("fail", 0),
    }


def append_quality_report(
    summary: BuildSummary,
    *,
    item: BuildItem,
    result,
    source_id: Optional[int],
    report: dict,
) -> None:
    """把单文档质量报告写入本次构建摘要，方便后台版本页查看。"""
    if summary.quality_reports is None:
        summary.quality_reports = []
    summary.quality_reports.append(
        {
            "document_id": item.document_id,
            "title": item.title or getattr(result, "title", ""),
            "kb_category": item.kb_category,
            "doc_type": item.doc_type,
            "prepared_file": item.prepared_file,
            "source_id": source_id or 0,
            "score": int(report.get("score") or 0),
            "grade": report.get("grade") or "",
            "status": report.get("status") or "",
            "dimensions": report.get("dimensions") or [],
            "findings": report.get("findings") or [],
            "recommendations": report.get("recommendations") or [],
            "metrics": report.get("metrics") or {},
        }
    )
    refresh_quality_overview(summary)


def reset_collection(collection: str, milvus_uri: str, milvus_token: str) -> None:
    try:
        from pymilvus import utility
        from pymilvus import connections
    except ImportError as exc:
        raise RuntimeError("重建 collection 需要 pymilvus 依赖") from exc

    alias = "slc_vector_builder"
    connection_args = {"uri": milvus_uri}
    if milvus_token:
        connection_args["token"] = milvus_token
    connections.connect(alias=alias, **connection_args)
    try:
        if utility.has_collection(collection, using=alias):
            logger.warning("Dropping Milvus collection: %s", collection)
            utility.drop_collection(collection, using=alias)
    finally:
        connections.disconnect(alias)


def index_items(
    *,
    manifest_path: Path,
    items: Iterable[BuildItem],
    tenant,
    source_model,
    service,
    db,
    summary: BuildSummary,
    dry_run: bool,
    strict: bool,
    quality_report_builder: Optional[Callable[..., object]] = None,
    progress_callback: Optional[Callable[[BuildSummary], None]] = None,
) -> BuildSummary:
    """批量把 manifest 中的文件写入 Milvus，并累计构建结果。"""
    for item in items:
        summary.total += 1
        document_path = resolve_document_path(manifest_path, item.prepared_file)
        source_id = find_source_id(db, source_model, tenant.id, item)
        if dry_run:
            logger.info(
                "[dry-run] %s | %s | %s | source_id=%s",
                item.document_id,
                item.kb_category,
                document_path,
                source_id or "-",
            )
            summary.skipped += 1
            continue
        try:
            result = service.index_file(
                path=document_path,
                filename=document_path.name,
                local_file=item.prepared_file,
                tenant_id=tenant.id,
                tenant_code=tenant.code,
                tenant_name=tenant.name,
                title=item.title,
                source_id=source_id,
                document_id=item.document_id,
                extra_metadata=extra_metadata(item),
            )
            summary.indexed += 1
            summary.document_indexed += 1
            summary.chunks += result.chunks
            quality_score = "-"
            if quality_report_builder:
                try:
                    quality_report = quality_report_builder(
                        result=result,
                        title=item.title or getattr(result, "title", ""),
                        source_id=source_id,
                        tenant_code=tenant.code,
                    )
                    append_quality_report(
                        summary,
                        item=item,
                        result=result,
                        source_id=source_id,
                        report=quality_report.model_dump(),
                    )
                    quality_score = summary.quality_reports[-1]["score"] if summary.quality_reports else "-"
                except Exception as exc:
                    if summary.quality_report_errors is None:
                        summary.quality_report_errors = []
                    if len(summary.quality_report_errors) < 20:
                        summary.quality_report_errors.append(
                            {
                                "document_id": item.document_id,
                                "title": item.title,
                                "error_type": exc.__class__.__name__,
                                "error": str(exc),
                            }
                        )
                    logger.exception("failed to build quality report for %s: %s", item.document_id, exc)
            logger.info(
                "indexed %s | chunks=%s | characters=%s | collection=%s | quality=%s",
                item.document_id,
                result.chunks,
                getattr(result, "characters", 0),
                getattr(result, "collection", summary.collection),
                quality_score,
            )
        except Exception as exc:
            summary.failed += 1
            if summary.errors is None:
                summary.errors = []
            if len(summary.errors) < 20:
                summary.errors.append(
                    {
                        "document_id": item.document_id,
                        "title": item.title,
                        "error_type": exc.__class__.__name__,
                        "error": str(exc),
                    }
                )
            logger.exception("failed to index %s: %s", item.document_id, exc)
            if strict:
                raise
        finally:
            if progress_callback:
                progress_callback(summary)
    return summary


def write_summary(path: str, summary: BuildSummary) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")

    manifest_path = Path(args.manifest).expanduser().resolve()
    categories = {item.strip() for item in args.categories.split(",") if item.strip()}
    items = filter_manifest_items(load_manifest(manifest_path, categories), include_manifest_faqs=args.include_manifest_faqs)
    if args.limit > 0:
        items = items[: args.limit]

    if args.dry_run:
        # dry-run 只检查 manifest 和文件路径，不连接 Milvus，适合部署前验证资料是否齐全。
        summary = BuildSummary(
            tenant_code=args.tenant_code,
            manifest=display_path(manifest_path),
            collection=os.getenv("MILVUS_COLLECTION", "slc_compliance_docs"),
            version=args.version or "dry-run",
            dry_run=True,
        )
        for item in items:
            summary.total += 1
            document_path = resolve_document_path(manifest_path, item.prepared_file)
            logger.info("[dry-run] %s | %s | %s", item.document_id, item.kb_category, display_path(document_path))
            summary.skipped += 1
        write_summary(args.summary_file, summary)
        logger.info("summary: %s", asdict(summary))
        return 0

    from app.database import SessionLocal, init_db
    from app.models import Source, Tenant
    from app.services.milvus_vector_service import MilvusVectorService
    from app.services.quality_reports import build_vector_ingest_quality_report
    from app.services.runtime_config import get_runtime_config
    from app.services.vector_version_service import (
        activate_version,
        base_collection_name,
        collection_name_for_version,
        create_or_replace_building_version,
        fail_version_build,
        finish_version_build,
        manifest_sha256,
        normalize_version_name,
    )

    init_db()
    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.code == args.tenant_code).first()
        if not tenant:
            raise SystemExit(f"tenant not found: {args.tenant_code}")
        runtime_config = get_runtime_config(db)
        version_name = normalize_version_name(args.version)
        # 构建时临时把 runtime_config.milvus_collection 替换成本次版本 collection，
        # 成功激活后才会写回系统配置，保证旧版本仍可继续服务。
        base_collection = args.base_collection or base_collection_name(runtime_config.milvus_collection, tenant)
        collection_name = args.collection_name or collection_name_for_version(
            base_collection,
            tenant,
            version_name,
        )
        runtime_config = replace(runtime_config, milvus_collection=collection_name)
        summary = BuildSummary(
            tenant_code=tenant.code,
            manifest=display_path(manifest_path),
            collection=runtime_config.milvus_collection,
            version=version_name,
            dry_run=args.dry_run,
        )
        version_record = create_or_replace_building_version(
            db,
            tenant=tenant,
            version=version_name,
            collection_name=collection_name,
            manifest_path=display_path(manifest_path),
            manifest_hash=manifest_sha256(manifest_path),
            categories=sorted(categories),
            embedding_model=runtime_config.langchain_embedding_model,
            chunk_size=runtime_config.vector_chunk_size,
            chunk_overlap=runtime_config.vector_chunk_overlap,
            created_by="vector-builder",
            description=args.description,
        )
        db.commit()
        service = MilvusVectorService(runtime_config)
        if not args.dry_run and not service.configured:
            error = "Milvus builder is not configured. Please set LANGCHAIN_API_KEY, embedding model, and MILVUS_URI."
            fail_version_build(db, version_record, error=error, summary=asdict(summary))
            db.commit()
            write_summary(args.summary_file, summary)
            logger.error(error)
            return 1
        def save_progress(current_summary: BuildSummary) -> None:
            finish_version_build(
                db,
                version_record,
                document_count=current_summary.total,
                indexed_count=current_summary.indexed,
                failed_count=current_summary.failed,
                chunk_count=current_summary.chunks,
                summary=asdict(current_summary),
            )
            version_record.status = "building"
            version_record.build_finished_at = None
            db.commit()

        try:
            if args.reset_collection and not args.dry_run:
                reset_collection(runtime_config.milvus_collection, runtime_config.milvus_uri, runtime_config.milvus_token)
            summary = index_items(
                manifest_path=manifest_path,
                items=items,
                tenant=tenant,
                source_model=Source,
                service=service,
                db=db,
                summary=summary,
                dry_run=args.dry_run,
                strict=args.strict,
                quality_report_builder=build_vector_ingest_quality_report,
                progress_callback=save_progress,
            )
            finish_version_build(
                db,
                version_record,
                document_count=summary.total,
                indexed_count=summary.indexed,
                failed_count=summary.failed,
                chunk_count=summary.chunks,
                summary=asdict(summary),
            )
            if args.activate and summary.failed == 0 and summary.indexed > 0:
                activate_version(db, version_record, activated_by="vector-builder")
            db.commit()
        except KeyboardInterrupt as exc:
            fail_version_build(db, version_record, error="vector build interrupted", summary=asdict(summary))
            db.commit()
            logger.exception("vector build interrupted")
            write_summary(args.summary_file, summary)
            return 130
        except Exception as exc:
            fail_version_build(db, version_record, error=str(exc), summary=asdict(summary))
            db.commit()
            logger.exception("vector build failed: %s", exc)
            write_summary(args.summary_file, summary)
            return 1

    write_summary(args.summary_file, summary)
    logger.info("summary: %s", asdict(summary))
    if summary.failed and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
