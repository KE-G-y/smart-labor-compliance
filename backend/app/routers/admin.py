"""管理端路由。"""
import csv
import io
import json
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.database import get_db, settings
from app.dependencies import get_admin_tenant_filter, get_current_admin, normalize_pagination, order_by_newest
from app.models import Admin, ChatLog, FAQ, Feedback, KnowledgePackage, Source, Tenant, TestQuestion
from app.response import ok, page as page_response
from app.schemas.admin import (
    AdminCreate,
    AdminLogin,
    AdminToken,
    AdminUpdate,
    SystemConfigResponse,
    SystemConfigUpdate,
    TenantCreate,
    TenantUpdate,
)
from app.schemas.faq import FAQCreate, FAQUpdate
from app.schemas.source import SourceCreate, SourceUpdate
from app.security import (
    ROLE_LABELS,
    ROLE_PERMISSIONS,
    SUPER_ADMIN_ROLES,
    TENANT_ADMIN_ROLES,
    authenticate_admin,
    create_access_token,
    get_password_hash,
    require_role,
    role_label,
    role_permissions,
    sanitize_text,
)
from app.services.dify_service import check_external_services
from app.services.runtime_config import (
    CONFIG_KEYS,
    get_runtime_config,
    normalize_config_update,
    set_db_config_value,
)

router = APIRouter(prefix="/api/admin", tags=["管理端"])

ALLOWED_SOURCE_FILE_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".html", ".htm", ".csv", ".xlsx", ".xls"}
ALLOWED_IMPORT_FILE_EXTENSIONS = {".csv"}
FAQ_EXPORT_FIELDS = ["id", "faq_code", "question", "answer", "category", "region", "risk_level", "keywords", "language", "effective_date"]
SOURCE_EXPORT_FIELDS = ["id", "source_code", "title", "url", "doc_type", "issuer", "region", "validity_status", "review_status", "reviewed_at", "reviewed_by", "local_file", "description"]
PACKAGE_EXPORT_FIELDS = ["id", "name", "region", "version", "description", "categories", "status", "dify_dataset_id", "ragflow_dataset_id"]


def _require_permission(current_admin: dict, permission: str) -> None:
    if permission not in current_admin.get("permissions", []):
        raise HTTPException(status_code=403, detail="当前账号没有该操作权限")


def _parse_ids(ids: Optional[str]) -> list[int]:
    if not ids:
        return []
    parsed: list[int] = []
    for raw in ids.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed.append(int(raw))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="无效的 ID 列表") from exc
    return parsed


def _read_json_list(value):
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (TypeError, json.JSONDecodeError):
        pass
    return [item.strip() for item in str(value).split("|") if item.strip()]


def _csv_text_response(filename: str, rows: list[dict], fields: list[str]) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        normalized = {}
        for field in fields:
            value = row.get(field)
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, datetime):
                value = value.isoformat(sep=" ", timespec="seconds")
            elif isinstance(value, date):
                value = value.isoformat()
            normalized[field] = "" if value is None else value
        writer.writerow(normalized)
    content = output.getvalue().encode("utf-8-sig")
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(io.BytesIO(content), media_type="text/csv; charset=utf-8", headers=headers)


async def _read_import_rows(file: UploadFile) -> list[dict]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMPORT_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="目前仅支持 CSV 文件导入")
    content = await file.read()
    await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="导入文件为空")
    text = content.decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(io.StringIO(text)) if any((value or "").strip() for value in row.values())]


def _module_query(db: Session, model, current_admin: dict, ids: Optional[str] = None, tenant_id: Optional[int] = None):
    query = _tenant_scoped_query(db, model, current_admin, tenant_id)
    parsed_ids = _parse_ids(ids)
    if parsed_ids:
        query = query.filter(model.id.in_(parsed_ids))
    return query


def _tenant_query(db: Session, current_admin: dict):
    query = db.query(Tenant)
    if current_admin["role"] != "super_admin":
        query = query.filter(Tenant.id == current_admin["tenant_id"])
    return query


def _serialize_admin(admin: Admin) -> dict:
    return {
        "id": admin.id,
        "tenant_id": admin.tenant_id,
        "tenant_name": admin.tenant.name if admin.tenant else "平台",
        "username": admin.username,
        "role": admin.role,
        "role_label": role_label(admin.role),
        "display_name": admin.display_name,
        "email": admin.email,
        "is_active": admin.is_active,
        "created_at": admin.created_at,
        "last_login_at": admin.last_login_at,
    }


def _serialize_tenant(tenant: Tenant) -> dict:
    return {
        "id": tenant.id,
        "code": tenant.code,
        "name": tenant.name,
        "industry": tenant.industry,
        "region": tenant.region,
        "contact_name": tenant.contact_name,
        "contact_email": tenant.contact_email,
        "contact_phone": tenant.contact_phone,
        "status": tenant.status,
        "is_demo": tenant.is_demo,
        "dify_configured": bool(tenant.dify_api_key),
        "ragflow_dataset_id": tenant.ragflow_dataset_id,
        "notes": tenant.notes,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at,
    }


def _tenant_scoped_query(db: Session, model, current_admin: dict, tenant_id: Optional[int] = None):
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)
    query = db.query(model)
    if allowed_tenant_id:
        query = query.filter(model.tenant_id == allowed_tenant_id)
    return query


def _find_duplicate_faq(db: Session, tenant_id: int, payload: dict, exclude_id: Optional[int] = None) -> Optional[FAQ]:
    filters = []
    if payload.get("faq_code"):
        filters.append(FAQ.faq_code == payload["faq_code"])
    if payload.get("question"):
        filters.append((FAQ.language == payload.get("language", "zh-CN")) & (FAQ.question == payload["question"]))
    if not filters:
        return None
    query = db.query(FAQ).filter(FAQ.tenant_id == tenant_id, or_(*filters))
    if exclude_id:
        query = query.filter(FAQ.id != exclude_id)
    return query.order_by(FAQ.id.asc()).first()


def _find_duplicate_source(db: Session, tenant_id: int, payload: dict, exclude_id: Optional[int] = None) -> Optional[Source]:
    filters = []
    if payload.get("source_code"):
        filters.append(Source.source_code == payload["source_code"])
    if payload.get("url"):
        filters.append(Source.url == payload["url"])
    if payload.get("title"):
        filters.append((Source.title == payload["title"]) & (Source.issuer == (payload.get("issuer") or "")))
    if not filters:
        return None
    query = db.query(Source).filter(Source.tenant_id == tenant_id, or_(*filters))
    if exclude_id:
        query = query.filter(Source.id != exclude_id)
    return query.order_by(Source.id.asc()).first()


def _is_source_reviewed(value: Optional[str]) -> bool:
    return value in {"已复核", "reviewed"}


def _reviewer_name(current_admin: dict) -> str:
    return current_admin.get("display_name") or current_admin.get("username") or f"管理员{current_admin.get('id')}"


def _source_similarity(left: str, right: str) -> float:
    left = (left or "").strip()
    right = (right or "").strip()
    if not left or not right:
        return 0
    if left == right:
        return 1
    if left in right or right in left:
        return 0.92
    return SequenceMatcher(None, left, right).ratio()


def _source_url_similarity(left: str, right: str) -> float:
    left = (left or "").strip()
    right = (right or "").strip()
    if not left or not right:
        return 0
    if left == right:
        return 1
    left_parts = urlparse(left)
    right_parts = urlparse(right)
    if left_parts.netloc != right_parts.netloc:
        return 0
    left_path = left_parts.path.strip("/")
    right_path = right_parts.path.strip("/")
    if len(left_path) < 8 or len(right_path) < 8:
        return 0
    if left_path in right_path or right_path in left_path:
        return 0.78
    return 0


def _sources_from_current_catalog(db: Session, tenant_id: int, log: ChatLog) -> list[dict]:
    """Return source snapshots with URLs corrected from the maintained source catalog."""
    raw_sources = log.sources if isinstance(log.sources, list) else []
    catalog = db.query(Source).filter(Source.tenant_id == tenant_id).all()
    used_ids: set[int] = set()
    corrected: list[dict] = []

    def source_to_dict(source: Source, snapshot: Optional[dict] = None) -> dict:
        used_ids.add(source.id)
        return {
            "id": source.id,
            "title": source.title,
            "url": source.url,
            "snippet": source.description or (snapshot or {}).get("snippet"),
            "review_status": source.review_status,
        }

    for item in raw_sources:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or ""
        url = item.get("url") or ""
        best = None
        best_score = 0.0
        for source in catalog:
            score = max(_source_similarity(title, source.title), _source_url_similarity(url, source.url or ""))
            if score > best_score:
                best = source
                best_score = score
        if best and best_score >= 0.62:
            corrected.append(source_to_dict(best, item))
        elif title or url:
            corrected.append({
                "title": title or url,
                "url": url,
                "snippet": item.get("snippet"),
                "review_status": item.get("review_status"),
            })

    faq = (
        db.query(FAQ)
        .filter(FAQ.tenant_id == tenant_id, FAQ.question == log.question)
        .order_by(FAQ.id.asc())
        .first()
    )
    if faq and faq.source_ids:
        faq_sources = (
            db.query(Source)
            .filter(Source.tenant_id == tenant_id, Source.id.in_(faq.source_ids))
            .order_by(Source.id.asc())
            .all()
        )
        for source in faq_sources:
            if source.id not in used_ids:
                corrected.append(source_to_dict(source))

    return corrected


def _safe_upload_filename(filename: str) -> str:
    raw_name = Path(filename or "source-file").name
    stem = sanitize_text(Path(raw_name).stem) or "source"
    suffix = Path(raw_name).suffix.lower()
    if suffix not in ALLOWED_SOURCE_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文件类型")
    safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in stem).strip("_") or "source"
    return f"{uuid4().hex}_{safe_stem[:80]}{suffix}"


@router.post("/login", response_model=AdminToken)
async def login(request: AdminLogin):
    admin = authenticate_admin(request.username.strip(), request.password, request.tenant_code)
    if not admin:
        raise HTTPException(status_code=401, detail="用户名、密码或租户不正确")

    access_token = create_access_token(
        data={
            "sub": str(admin["id"]),
            "role": admin["role"],
            "tenant_id": admin["tenant_id"],
        }
    )

    return AdminToken(
        access_token=access_token,
        admin_id=admin["id"],
        username=admin["username"],
        role=admin["role"],
        role_label=role_label(admin["role"]),
        permissions=role_permissions(admin["role"]),
        tenant_id=admin["tenant_id"],
        tenant_code=admin["tenant_code"],
        tenant_name=admin["tenant_name"],
    )


@router.get("/verify-token")
async def verify_token(current_admin: dict = Depends(get_current_admin)):
    return ok(current_admin)


@router.get("/roles")
async def get_roles(current_admin: dict = Depends(get_current_admin)):
    roles = [
        {"value": role, "label": label, "permissions": ROLE_PERMISSIONS.get(role, [])}
        for role, label in ROLE_LABELS.items()
    ]
    if current_admin["role"] != "super_admin":
        roles = [item for item in roles if item["value"] != "super_admin"]
    return ok(roles)


@router.get("/statistics")
async def get_statistics(
    tenant_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)

    def scoped(model):
        query = db.query(model)
        return query.filter(model.tenant_id == allowed_tenant_id) if allowed_tenant_id else query

    chat_query = scoped(ChatLog)
    feedback_query = scoped(Feedback)
    faq_query = scoped(FAQ)
    source_query = scoped(Source)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_feedbacks = feedback_query.count()
    helpful = feedback_query.filter(Feedback.is_helpful.is_(True)).count()
    helpful_rate = int(round((helpful / total_feedbacks) * 100)) if total_feedbacks else 0
    avg_response = chat_query.with_entities(func.avg(ChatLog.response_time)).scalar() or 0

    top_questions = (
        chat_query.with_entities(ChatLog.question, func.count(ChatLog.id).label("count"))
        .group_by(ChatLog.question)
        .order_by(desc("count"))
        .limit(5)
        .all()
    )

    data = {
        "total_questions": chat_query.count(),
        "today_questions": chat_query.filter(ChatLog.created_at >= today).count(),
        "total_feedbacks": total_feedbacks,
        "pending_feedbacks": feedback_query.filter(Feedback.status == "pending").count(),
        "total_faqs": faq_query.count(),
        "total_sources": source_query.count(),
        "total_tenants": db.query(Tenant).count() if current_admin["role"] == "super_admin" else 1,
        "helpful_rate": helpful_rate,
        "avg_response_time": int(avg_response),
        "top_questions": [{"question": row.question, "count": row.count} for row in top_questions],
        "services": check_external_services(),
    }
    return ok(data)


@router.get("/system-config")
async def get_system_config(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    require_role(current_admin["role"], SUPER_ADMIN_ROLES)
    runtime_config = get_runtime_config(db)
    return ok(SystemConfigResponse(
        dify_base_url=runtime_config.dify_base_url,
        dify_api_key_configured=bool(runtime_config.dify_api_key),
        dify_timeout_seconds=runtime_config.dify_timeout_seconds,
        ragflow_base_url=runtime_config.ragflow_base_url,
        ragflow_web_url=runtime_config.ragflow_web_url,
        ragflow_api_key_configured=bool(runtime_config.ragflow_api_key),
        ragflow_timeout_seconds=runtime_config.ragflow_timeout_seconds,
    ))


@router.put("/system-config")
async def update_system_config(
    request: SystemConfigUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    require_role(current_admin["role"], SUPER_ADMIN_ROLES)
    updates = request.model_dump(exclude_unset=True)

    normalized_updates = {}
    for key, value in updates.items():
        if key not in CONFIG_KEYS:
            continue
        try:
            normalized_updates[key] = normalize_config_update(key, value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    for key, value in normalized_updates.items():
        set_db_config_value(db, key, value)
    db.commit()
    return ok({"message": "配置更新成功"}, "配置更新成功")


@router.get("/tenants")
async def get_tenants(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    page, page_size = normalize_pagination(page, page_size)
    query = _tenant_query(db, current_admin)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter((Tenant.name.like(like)) | (Tenant.code.like(like)))
    if status:
        query = query.filter(Tenant.status == status)
    total = query.count()
    tenants = order_by_newest(query, Tenant).offset((page - 1) * page_size).limit(page_size).all()
    return page_response([_serialize_tenant(item) for item in tenants], total, page, page_size)


@router.post("/tenants")
async def create_tenant(
    request: TenantCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    require_role(current_admin["role"], SUPER_ADMIN_ROLES)
    code = request.code.strip()
    if db.query(Tenant).filter(Tenant.code == code).first():
        raise HTTPException(status_code=400, detail="租户编码已存在")
    tenant = Tenant(
        code=code,
        name=request.name.strip(),
        industry=request.industry,
        region=request.region,
        contact_name=request.contact_name,
        contact_email=request.contact_email,
        contact_phone=request.contact_phone,
        status=request.status,
        notes=sanitize_text(request.notes),
    )
    db.add(tenant)
    db.flush()

    if request.admin_username and request.admin_password:
        db.add(
            Admin(
                tenant_id=tenant.id,
                username=request.admin_username.strip(),
                password_hash=get_password_hash(request.admin_password),
                role="tenant_admin",
                display_name=f"{tenant.name}管理员",
                is_active=True,
            )
        )

    db.commit()
    db.refresh(tenant)
    return ok(_serialize_tenant(tenant), "租户创建成功")


@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    request: TenantUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    if current_admin["role"] != "super_admin" and tenant_id != current_admin.get("tenant_id"):
        raise HTTPException(status_code=403, detail="不能修改其他租户")
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(tenant, field, sanitize_text(value) if isinstance(value, str) else value)
    db.commit()
    db.refresh(tenant)
    return ok(_serialize_tenant(tenant), "租户更新成功")


@router.get("/admins")
async def get_admins(
    tenant_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    require_role(current_admin["role"], TENANT_ADMIN_ROLES)
    page, page_size = normalize_pagination(page, page_size)
    query = db.query(Admin)
    if current_admin["role"] == "super_admin":
        if tenant_id is not None:
            query = query.filter(Admin.tenant_id == tenant_id)
    else:
        query = query.filter(Admin.tenant_id == current_admin["tenant_id"], Admin.role != "super_admin")
    total = query.count()
    admins = order_by_newest(query, Admin).offset((page - 1) * page_size).limit(page_size).all()
    return page_response([_serialize_admin(item) for item in admins], total, page, page_size)


@router.post("/admins")
async def create_admin_account(
    request: AdminCreate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    require_role(current_admin["role"], TENANT_ADMIN_ROLES)
    role = request.role
    if role not in ROLE_LABELS:
        raise HTTPException(status_code=400, detail="无效的角色")
    if role == "super_admin" and current_admin["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="不能创建超级管理员")

    tenant_id = request.tenant_id if current_admin["role"] == "super_admin" else current_admin["tenant_id"]
    if role != "super_admin" and not tenant_id:
        raise HTTPException(status_code=400, detail="非平台管理员必须绑定租户")

    username = request.username.strip()
    if db.query(Admin).filter(Admin.username == username, Admin.tenant_id == tenant_id).first():
        raise HTTPException(status_code=400, detail="该租户下用户名已存在")

    admin = Admin(
        tenant_id=tenant_id,
        username=username,
        password_hash=get_password_hash(request.password),
        role=role,
        display_name=sanitize_text(request.display_name),
        email=request.email,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return ok(_serialize_admin(admin), "账号创建成功")


@router.put("/admins/{admin_id}")
async def update_admin_account(
    admin_id: int,
    request: AdminUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    require_role(current_admin["role"], TENANT_ADMIN_ROLES)
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="账号不存在")
    if current_admin["role"] != "super_admin" and admin.tenant_id != current_admin["tenant_id"]:
        raise HTTPException(status_code=403, detail="不能修改其他租户账号")
    if admin.role == "super_admin" and current_admin["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="不能修改超级管理员")

    update_data = request.model_dump(exclude_unset=True)
    if "role" in update_data and update_data["role"]:
        if update_data["role"] == "super_admin" and current_admin["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="不能授予超级管理员")
        admin.role = update_data["role"]
    if update_data.get("password"):
        admin.password_hash = get_password_hash(update_data["password"])
    for field in ["display_name", "email", "is_active"]:
        if field in update_data:
            setattr(admin, field, sanitize_text(update_data[field]) if isinstance(update_data[field], str) else update_data[field])
    db.commit()
    db.refresh(admin)
    return ok(_serialize_admin(admin), "账号更新成功")


@router.delete("/admins/{admin_id}")
async def delete_admin_account(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    require_role(current_admin["role"], TENANT_ADMIN_ROLES)
    if admin_id == current_admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="账号不存在")
    if current_admin["role"] != "super_admin" and admin.tenant_id != current_admin["tenant_id"]:
        raise HTTPException(status_code=403, detail="不能删除其他租户账号")
    if admin.role == "super_admin":
        raise HTTPException(status_code=403, detail="不能删除超级管理员")
    db.delete(admin)
    db.commit()
    return ok(message="账号删除成功")


@router.get("/logs")
async def get_logs(
    tenant_id: Optional[int] = None,
    user_id: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    page, page_size = normalize_pagination(page, page_size)
    query = _tenant_scoped_query(db, ChatLog, current_admin, tenant_id)
    if user_id:
        query = query.filter(ChatLog.user_id == user_id)
    if keyword:
        query = query.filter(ChatLog.question.contains(keyword))
    if status:
        query = query.filter(ChatLog.status == status)
    if start_date:
        query = query.filter(ChatLog.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(ChatLog.created_at < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    total = query.count()
    logs = order_by_newest(query, ChatLog).offset((page - 1) * page_size).limit(page_size).all()
    return page_response(
        [
            {
                "id": item.id,
                "tenant_id": item.tenant_id,
                "tenant_name": item.tenant.name if item.tenant else "",
                "user_id": item.user_id,
                "question": item.question,
                "answer": item.answer,
                "provider": item.provider,
                "risk_level": item.risk_level,
                "response_time": item.response_time,
                "status": item.status,
                "created_at": item.created_at,
            }
            for item in logs
        ],
        total,
        page,
        page_size,
    )


@router.get("/logs/{log_id}")
async def get_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    log = db.query(ChatLog).filter(ChatLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")
    get_admin_tenant_filter(current_admin, log.tenant_id)
    return ok(
        {
            "id": log.id,
            "tenant_id": log.tenant_id,
            "tenant_name": log.tenant.name if log.tenant else "",
            "user_id": log.user_id,
            "session_id": log.session_id,
            "conversation_id": log.conversation_id,
            "language": log.language,
            "question": log.question,
            "answer": log.answer,
            "sources": _sources_from_current_catalog(db, log.tenant_id, log),
            "related_tasks": log.related_tasks,
            "provider": log.provider,
            "risk_level": log.risk_level,
            "response_time": log.response_time,
            "status": log.status,
            "created_at": log.created_at,
        }
    )


@router.get("/faqs")
async def get_faqs(
    tenant_id: Optional[int] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "faqs")
    page, page_size = normalize_pagination(page, page_size)
    query = _tenant_scoped_query(db, FAQ, current_admin, tenant_id)
    if category:
        query = query.filter(FAQ.category == category)
    if keyword:
        query = query.filter(or_(FAQ.question.contains(keyword), FAQ.faq_code.contains(keyword)))
    total = query.count()
    items = order_by_newest(query, FAQ).offset((page - 1) * page_size).limit(page_size).all()
    return page_response(items, total, page, page_size)


@router.get("/faqs/export")
async def export_faqs(
    tenant_id: Optional[int] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    ids: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "faqs_export")
    query = _module_query(db, FAQ, current_admin, ids, tenant_id)
    if category:
        query = query.filter(FAQ.category == category)
    if keyword:
        query = query.filter(or_(FAQ.question.contains(keyword), FAQ.faq_code.contains(keyword)))
    rows = [
        {
            "id": item.id,
            "faq_code": item.faq_code,
            "question": item.question,
            "answer": item.answer,
            "category": item.category,
            "region": item.region,
            "risk_level": item.risk_level,
            "keywords": item.keywords or [],
            "language": item.language,
            "effective_date": item.effective_date,
        }
        for item in order_by_newest(query, FAQ).all()
    ]
    return _csv_text_response("faqs.csv", rows, FAQ_EXPORT_FIELDS)


@router.post("/faqs/import")
async def import_faqs(
    tenant_id: Optional[int] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "faqs_import")
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)
    rows = await _read_import_rows(file)
    imported = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        question = sanitize_text(row.get("question") or row.get("问题"))
        answer = sanitize_text(row.get("answer") or row.get("回答") or row.get("答案"))
        if not question or not answer:
            skipped += 1
            errors.append(f"第 {index} 行缺少 question/answer")
            continue
        payload = {
            "faq_code": row.get("faq_code") or row.get("编码") or None,
            "question": question,
            "answer": answer,
            "category": row.get("category") or row.get("分类") or None,
            "region": row.get("region") or row.get("地区") or "陕西",
            "risk_level": row.get("risk_level") or row.get("风险等级") or "medium",
            "keywords": _read_json_list(row.get("keywords") or row.get("关键词")),
            "aliases": _read_json_list(row.get("aliases")),
            "source_ids": _read_json_list(row.get("source_ids")),
            "language": row.get("language") or "zh-CN",
            "effective_date": row.get("effective_date") or None,
        }
        faq = _find_duplicate_faq(db, allowed_tenant_id, payload)
        if faq:
            for field, value in payload.items():
                setattr(faq, field, value)
            updated += 1
        else:
            db.add(FAQ(tenant_id=allowed_tenant_id, **payload))
            imported += 1
    db.commit()
    return ok({"imported": imported, "updated": updated, "skipped": skipped, "errors": errors[:20]}, "FAQ 导入完成")


@router.post("/faqs/batch")
async def batch_faqs(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "faqs_batch")
    ids = request.get("ids") or []
    action = request.get("action")
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要批量操作的数据")
    query = _tenant_scoped_query(db, FAQ, current_admin).filter(FAQ.id.in_(ids))
    items = query.all()
    if action == "delete":
        for item in items:
            db.delete(item)
    elif action == "set_risk":
        risk_level = request.get("risk_level")
        if risk_level not in {"low", "medium", "high"}:
            raise HTTPException(status_code=400, detail="无效的风险等级")
        for item in items:
            item.risk_level = risk_level
    else:
        raise HTTPException(status_code=400, detail="不支持的批量操作")
    db.commit()
    return ok({"affected": len(items)}, "批量操作完成")


@router.post("/faqs")
async def create_faq(
    request: FAQCreate,
    tenant_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "faqs")
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)
    payload = {
        "faq_code": request.faq_code,
        "question": sanitize_text(request.question),
        "answer": sanitize_text(request.answer),
        "category": request.category,
        "region": request.region,
        "risk_level": request.risk_level,
        "keywords": request.keywords,
        "aliases": request.aliases,
        "source_ids": request.source_ids,
        "language": request.language,
        "effective_date": request.effective_date,
    }
    faq = _find_duplicate_faq(db, allowed_tenant_id, payload)
    if faq:
        for field, value in payload.items():
            setattr(faq, field, value)
        message = "FAQ 已存在，已覆盖更新"
    else:
        faq = FAQ(tenant_id=allowed_tenant_id, **payload)
        db.add(faq)
        message = "FAQ 添加成功"
    db.commit()
    db.refresh(faq)
    return ok(faq, message)


@router.put("/faqs/{faq_id}")
async def update_faq(
    faq_id: int,
    request: FAQUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "faqs")
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ 不存在")
    get_admin_tenant_filter(current_admin, faq.tenant_id)
    update_data = request.model_dump(exclude_unset=True)
    candidate = {
        "faq_code": update_data.get("faq_code", faq.faq_code),
        "question": sanitize_text(update_data.get("question", faq.question)),
        "language": update_data.get("language", faq.language),
    }
    if _find_duplicate_faq(db, faq.tenant_id, candidate, exclude_id=faq.id):
        raise HTTPException(status_code=400, detail="该租户下已存在相同 FAQ 编码或问题")
    for field, value in update_data.items():
        setattr(faq, field, sanitize_text(value) if field in {"question", "answer"} else value)
    db.commit()
    db.refresh(faq)
    return ok(faq, "FAQ 更新成功")


@router.delete("/faqs/{faq_id}")
async def delete_faq(
    faq_id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "faqs")
    faq = db.query(FAQ).filter(FAQ.id == faq_id).first()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ 不存在")
    get_admin_tenant_filter(current_admin, faq.tenant_id)
    db.delete(faq)
    db.commit()
    return ok(message="FAQ 删除成功")


@router.get("/sources")
async def get_sources(
    tenant_id: Optional[int] = None,
    doc_type: Optional[str] = None,
    region: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "sources")
    page, page_size = normalize_pagination(page, page_size)
    query = _tenant_scoped_query(db, Source, current_admin, tenant_id)
    if doc_type:
        query = query.filter(Source.doc_type == doc_type)
    if region:
        query = query.filter(Source.region == region)
    if keyword:
        query = query.filter(or_(Source.title.contains(keyword), Source.source_code.contains(keyword), Source.url.contains(keyword)))
    total = query.count()
    items = order_by_newest(query, Source).offset((page - 1) * page_size).limit(page_size).all()
    return page_response(items, total, page, page_size)


@router.get("/sources/export")
async def export_sources(
    tenant_id: Optional[int] = None,
    doc_type: Optional[str] = None,
    region: Optional[str] = None,
    keyword: Optional[str] = None,
    ids: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "sources_export")
    query = _module_query(db, Source, current_admin, ids, tenant_id)
    if doc_type:
        query = query.filter(Source.doc_type == doc_type)
    if region:
        query = query.filter(Source.region == region)
    if keyword:
        query = query.filter(or_(Source.title.contains(keyword), Source.source_code.contains(keyword), Source.url.contains(keyword)))
    rows = [
        {
            "id": item.id,
            "source_code": item.source_code,
            "title": item.title,
            "url": item.url,
            "doc_type": item.doc_type,
            "issuer": item.issuer,
            "region": item.region,
            "validity_status": item.validity_status,
            "review_status": item.review_status,
            "reviewed_at": item.reviewed_at,
            "reviewed_by": item.reviewed_by,
            "local_file": item.local_file,
            "description": item.description,
        }
        for item in order_by_newest(query, Source).all()
    ]
    return _csv_text_response("sources.csv", rows, SOURCE_EXPORT_FIELDS)


@router.post("/sources/import")
async def import_sources(
    tenant_id: Optional[int] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "sources_import")
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)
    rows = await _read_import_rows(file)
    imported = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        title = sanitize_text(row.get("title") or row.get("标题"))
        url = (row.get("url") or row.get("链接") or "").strip()
        local_file = (row.get("local_file") or row.get("本地文件") or "").strip()
        if not title or (not url and not local_file):
            skipped += 1
            errors.append(f"第 {index} 行缺少 title 或来源路径")
            continue
        payload = {
            "source_code": row.get("source_code") or row.get("编码") or None,
            "title": title,
            "url": url or None,
            "doc_type": row.get("doc_type") or row.get("类型") or None,
            "issuer": row.get("issuer") or row.get("发布机关") or "",
            "region": row.get("region") or row.get("地区") or None,
            "validity_status": row.get("validity_status") or "有效",
            "review_status": row.get("review_status") or "待人工复核",
            "owner": row.get("owner") or None,
            "local_file": local_file or None,
            "description": sanitize_text(row.get("description") or row.get("说明")),
        }
        if _is_source_reviewed(payload.get("review_status")):
            payload["reviewed_at"] = datetime.utcnow()
            payload["reviewed_by"] = _reviewer_name(current_admin)
        source = _find_duplicate_source(db, allowed_tenant_id, payload)
        if source:
            if _is_source_reviewed(source.review_status):
                skipped += 1
                errors.append(f"第 {index} 行匹配到已复核来源，已跳过")
                continue
            for field, value in payload.items():
                setattr(source, field, value)
            updated += 1
        else:
            db.add(Source(tenant_id=allowed_tenant_id, **payload))
            imported += 1
    db.commit()
    return ok({"imported": imported, "updated": updated, "skipped": skipped, "errors": errors[:20]}, "来源导入完成")


@router.post("/sources/batch")
async def batch_sources(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "sources_batch")
    ids = request.get("ids") or []
    action = request.get("action")
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要批量操作的数据")
    items = _tenant_scoped_query(db, Source, current_admin).filter(Source.id.in_(ids)).all()
    if action == "delete":
        for item in items:
            if _is_source_reviewed(item.review_status):
                raise HTTPException(status_code=400, detail="已复核的数据不支持批量删除")
            db.delete(item)
    elif action == "mark_reviewed":
        for item in items:
            item.review_status = "已复核"
            item.reviewed_at = datetime.utcnow()
            item.reviewed_by = _reviewer_name(current_admin)
    elif action == "mark_pending":
        for item in items:
            item.review_status = "待人工复核"
            item.reviewed_at = None
            item.reviewed_by = None
    else:
        raise HTTPException(status_code=400, detail="不支持的批量操作")
    db.commit()
    return ok({"affected": len(items)}, "批量操作完成")


@router.post("/sources")
async def create_source(
    request: SourceCreate,
    tenant_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "sources")
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)
    payload = request.model_dump()
    payload["issuer"] = payload.get("issuer") or ""
    if _is_source_reviewed(payload.get("review_status")):
        payload["reviewed_at"] = datetime.utcnow()
        payload["reviewed_by"] = _reviewer_name(current_admin)
    else:
        payload["reviewed_at"] = None
        payload["reviewed_by"] = None
    source = _find_duplicate_source(db, allowed_tenant_id, payload)
    if source:
        if _is_source_reviewed(source.review_status):
            raise HTTPException(status_code=400, detail="已复核的数据不支持编辑，请在详情中查看复核记录")
        for field, value in payload.items():
            setattr(source, field, value)
        message = "来源已存在，已覆盖更新"
    else:
        source = Source(tenant_id=allowed_tenant_id, **payload)
        db.add(source)
        message = "来源添加成功"
    db.commit()
    db.refresh(source)
    return ok(source, message)


@router.post("/sources/upload")
async def upload_source_file(
    tenant_id: Optional[int] = None,
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "sources")
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)
    if not allowed_tenant_id:
        raise HTTPException(status_code=400, detail="上传文件必须绑定租户")

    safe_name = _safe_upload_filename(file.filename)
    upload_root = Path(settings.upload_dir).resolve()
    target_dir = upload_root / f"tenant_{allowed_tenant_id}" / "sources"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name

    size = 0
    try:
        with target_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    target_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="上传文件过大")
                output.write(chunk)
    finally:
        await file.close()

    relative_path = target_path.relative_to(upload_root).as_posix()
    return ok(
        {
            "filename": file.filename,
            "stored_name": safe_name,
            "local_file": relative_path,
            "size": size,
        },
        "文件上传成功",
    )


@router.put("/sources/{source_id}")
async def update_source(
    source_id: int,
    request: SourceUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "sources")
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="来源不存在")
    get_admin_tenant_filter(current_admin, source.tenant_id)
    update_data = request.model_dump(exclude_unset=True)
    is_review_only = set(update_data) == {"review_status"}
    if _is_source_reviewed(source.review_status) and not is_review_only:
        raise HTTPException(status_code=400, detail="已复核的数据不支持编辑，请在详情中查看复核记录")
    next_url = update_data.get("url", source.url)
    next_local_file = update_data.get("local_file", source.local_file)
    if not (next_url or "").strip() and not (next_local_file or "").strip():
        raise HTTPException(status_code=400, detail="外部链接与上传文件必须至少填写一个")
    candidate = {
        "source_code": update_data.get("source_code", source.source_code),
        "url": next_url,
        "title": update_data.get("title", source.title),
        "issuer": update_data.get("issuer", source.issuer) or "",
    }
    if _find_duplicate_source(db, source.tenant_id, candidate, exclude_id=source.id):
        raise HTTPException(status_code=400, detail="该租户下已存在相同来源编码、链接或标题发布机构")
    for field, value in update_data.items():
        if field == "issuer":
            value = value or ""
        setattr(source, field, value)
    if "review_status" in update_data:
        if _is_source_reviewed(source.review_status):
            source.reviewed_at = datetime.utcnow()
            source.reviewed_by = _reviewer_name(current_admin)
        else:
            source.reviewed_at = None
            source.reviewed_by = None
    db.commit()
    db.refresh(source)
    return ok(source, "来源更新成功")


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "sources")
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="来源不存在")
    get_admin_tenant_filter(current_admin, source.tenant_id)
    db.delete(source)
    db.commit()
    return ok(message="来源删除成功")


@router.get("/knowledge-packages")
async def get_knowledge_packages(
    tenant_id: Optional[int] = None,
    region: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "packages")
    page, page_size = normalize_pagination(page, page_size)
    query = _tenant_scoped_query(db, KnowledgePackage, current_admin, tenant_id)
    if region:
        query = query.filter(KnowledgePackage.region == region)
    if status:
        query = query.filter(KnowledgePackage.status == status)
    total = query.count()
    packages = order_by_newest(query, KnowledgePackage).offset((page - 1) * page_size).limit(page_size).all()
    data = []
    for pkg in packages:
        data.append(
            {
                "id": pkg.id,
                "tenant_id": pkg.tenant_id,
                "tenant_name": pkg.tenant.name if pkg.tenant else "",
                "name": pkg.name,
                "region": pkg.region,
                "version": pkg.version,
                "description": pkg.description,
                "categories": pkg.categories or [],
                "status": pkg.status,
                "faq_count": db.query(FAQ).filter(FAQ.tenant_id == pkg.tenant_id).count(),
                "doc_count": db.query(Source).filter(Source.tenant_id == pkg.tenant_id).count(),
                "created_at": pkg.created_at,
                "updated_at": pkg.updated_at,
            }
        )
    return page_response(data, total, page, page_size)


@router.get("/knowledge-packages/export")
async def export_knowledge_packages(
    tenant_id: Optional[int] = None,
    region: Optional[str] = None,
    status: Optional[str] = None,
    ids: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "packages_export")
    query = _module_query(db, KnowledgePackage, current_admin, ids, tenant_id)
    if region:
        query = query.filter(KnowledgePackage.region == region)
    if status:
        query = query.filter(KnowledgePackage.status == status)
    rows = [
        {
            "id": item.id,
            "name": item.name,
            "region": item.region,
            "version": item.version,
            "description": item.description,
            "categories": item.categories or [],
            "status": item.status,
            "dify_dataset_id": item.dify_dataset_id,
            "ragflow_dataset_id": item.ragflow_dataset_id,
        }
        for item in order_by_newest(query, KnowledgePackage).all()
    ]
    return _csv_text_response("knowledge-packages.csv", rows, PACKAGE_EXPORT_FIELDS)


@router.post("/knowledge-packages/import")
async def import_knowledge_packages(
    tenant_id: Optional[int] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "packages_import")
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)
    rows = await _read_import_rows(file)
    imported = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        name = sanitize_text(row.get("name") or row.get("名称"))
        if not name:
            skipped += 1
            errors.append(f"第 {index} 行缺少 name")
            continue
        payload = {
            "name": name,
            "region": row.get("region") or row.get("地区") or None,
            "version": row.get("version") or row.get("版本") or "v1.0",
            "description": sanitize_text(row.get("description") or row.get("说明")),
            "categories": _read_json_list(row.get("categories") or row.get("分类")),
            "status": row.get("status") or row.get("状态") or "active",
            "dify_dataset_id": row.get("dify_dataset_id") or None,
            "ragflow_dataset_id": row.get("ragflow_dataset_id") or None,
        }
        if payload["status"] not in {"active", "disabled", "draft"}:
            payload["status"] = "active"
        package = (
            db.query(KnowledgePackage)
            .filter(KnowledgePackage.tenant_id == allowed_tenant_id, KnowledgePackage.name == payload["name"])
            .order_by(KnowledgePackage.id.asc())
            .first()
        )
        if package:
            for field, value in payload.items():
                setattr(package, field, value)
            updated += 1
        else:
            db.add(KnowledgePackage(tenant_id=allowed_tenant_id, **payload))
            imported += 1
    db.commit()
    return ok({"imported": imported, "updated": updated, "skipped": skipped, "errors": errors[:20]}, "知识包导入完成")


@router.post("/knowledge-packages/batch")
async def batch_knowledge_packages(
    request: dict,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "packages_batch")
    ids = request.get("ids") or []
    action = request.get("action")
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要批量操作的数据")
    items = _tenant_scoped_query(db, KnowledgePackage, current_admin).filter(KnowledgePackage.id.in_(ids)).all()
    if action == "delete":
        for item in items:
            db.delete(item)
    elif action == "set_status":
        status = request.get("status")
        if status not in {"active", "disabled", "draft"}:
            raise HTTPException(status_code=400, detail="无效的状态")
        for item in items:
            item.status = status
    else:
        raise HTTPException(status_code=400, detail="不支持的批量操作")
    db.commit()
    return ok({"affected": len(items)}, "批量操作完成")


@router.put("/knowledge-packages/{package_id}/status")
async def update_package_status(
    package_id: int,
    request: dict,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "packages")
    package = db.query(KnowledgePackage).filter(KnowledgePackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="知识包不存在")
    get_admin_tenant_filter(current_admin, package.tenant_id)
    status = request.get("status")
    if status not in {"active", "disabled", "draft"}:
        raise HTTPException(status_code=400, detail="无效的状态")
    package.status = status
    db.commit()
    return ok(message="状态更新成功")


@router.get("/test-questions")
async def get_test_questions(
    tenant_id: Optional[int] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "test_questions")
    page, page_size = normalize_pagination(page, page_size)
    query = _tenant_scoped_query(db, TestQuestion, current_admin, tenant_id)
    if category:
        query = query.filter(TestQuestion.category == category)
    total = query.count()
    items = order_by_newest(query, TestQuestion).offset((page - 1) * page_size).limit(page_size).all()
    return page_response(items, total, page, page_size)


@router.get("/service-status")
async def service_status(current_admin: dict = Depends(get_current_admin)):
    return ok(
        {
            "database": {
                "host": settings.db_host,
                "port": settings.db_port,
                "name": settings.db_name,
                "engine": "MySQL 8 / Docker",
            },
            "external_services": check_external_services(),
        }
    )
