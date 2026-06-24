"""用户端问答路由。"""
import csv
import io
import json
import time
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.database import get_db, settings
from app.dependencies import get_public_tenant, normalize_pagination
from app.models import ChatLog, Tenant
from app.response import ok
from app.schemas.chat import ChatRequest, ChatResponse, ChatStopRequest, HistoryResponse
from app.security import hash_ip, sanitize_text
from app.services.dify_service import ChatAttachment, ComplianceAnswerService, dify_attachment_capability
from app.services.quality_reports import build_answer_quality_report

router = APIRouter(prefix="/api", tags=["问答"])

HISTORY_EXPORT_FIELDS = [
    "id",
    "user_id",
    "session_id",
    "conversation_id",
    "language",
    "question",
    "answer",
    "sources",
    "related_tasks",
    "provider",
    "risk_level",
    "response_time",
    "status",
    "created_at",
]


def _elapsed_ms(start_time: float) -> int:
    """计算接口完整耗时，单位毫秒。"""
    return max(0, int((time.perf_counter() - start_time) * 1000))


async def _resolve_tenant(requested_tenant_code: Optional[str], header_tenant: Tenant, db: Session) -> Tenant:
    tenant = header_tenant
    if requested_tenant_code and requested_tenant_code != header_tenant.code:
        tenant = db.query(Tenant).filter(Tenant.code == requested_tenant_code, Tenant.status == "active").first()
        if not tenant:
            raise HTTPException(status_code=404, detail="租户不存在或已停用")
    return tenant


def _persist_chat_log(
    db: Session,
    tenant: Tenant,
    request: Request,
    *,
    session_id: str,
    user_id: str,
    language: str,
    question: str,
    response: ChatResponse,
    response_time: Optional[int] = None,
) -> ChatResponse:
    if response_time is not None:
        response.response_time = response_time
    trace_metrics = dict(response.trace_metrics or {})
    quality_start = time.perf_counter()
    response.evaluation = build_answer_quality_report(
        question=question,
        answer=response.answer,
        sources=response.sources,
        provider=response.provider,
        risk_level=response.risk_level,
        fallback_reason=response.fallback_reason,
        response_time_ms=response.response_time,
        trace_metrics=trace_metrics,
    ).model_dump()
    trace_metrics["quality_report_ms"] = max(0, int((time.perf_counter() - quality_start) * 1000))
    if response.evaluation:
        response.evaluation.setdefault("metrics", {})["trace"] = trace_metrics
    response.trace_metrics = trace_metrics
    chat_log = ChatLog(
        tenant_id=tenant.id,
        user_id=user_id,
        session_id=session_id,
        conversation_id=response.conversation_id,
        language=language,
        question=question,
        answer=response.answer,
        sources=[item.model_dump() for item in response.sources] if response.sources else None,
        related_tasks=[item.model_dump() for item in response.related_tasks] if response.related_tasks else None,
        provider=response.provider,
        risk_level=response.risk_level,
        evaluation=response.evaluation,
        response_time=response.response_time,
        status="success",
        client_ip_hash=hash_ip(request.client.host if request.client else None),
    )
    db.add(chat_log)
    db.commit()
    db.refresh(chat_log)
    response.question_id = chat_log.id
    return response


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


def _history_query(
    db: Session,
    tenant: Tenant,
    user_id: str,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
):
    query = db.query(ChatLog).filter(ChatLog.tenant_id == tenant.id, ChatLog.user_id == sanitize_text(user_id))
    keyword = sanitize_text(keyword)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(ChatLog.question.like(like), ChatLog.answer.like(like)))
    if status:
        query = query.filter(ChatLog.status == sanitize_text(status))
    if provider:
        query = query.filter(ChatLog.provider == sanitize_text(provider))
    return query


def _serialize_history_item(item: ChatLog) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "user_id": item.user_id,
        "session_id": item.session_id,
        "conversation_id": item.conversation_id,
        "language": item.language,
        "question": item.question,
        "answer": item.answer,
        "sources": item.sources,
        "related_tasks": item.related_tasks,
        "provider": item.provider,
        "risk_level": item.risk_level,
        "evaluation": item.evaluation,
        "response_time": item.response_time,
        "status": item.status,
        "created_at": item.created_at,
    }


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


@router.post("/chat", response_model=dict)
async def chat(
    request_data: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    header_tenant: Tenant = Depends(get_public_tenant),
):
    request_start = time.perf_counter()
    if not request_data.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    tenant = await _resolve_tenant(request_data.tenant_code, header_tenant, db)

    session_id = request_data.session_id or str(uuid.uuid4())
    user_id = sanitize_text(request_data.user_id) or "anonymous"
    question = sanitize_text(request_data.question) or ""
    user_role = sanitize_text(request_data.user_role) or "employee"
    province = sanitize_text(request_data.province) or "陕西省"
    city = sanitize_text(request_data.city) or "西安市"
    answer_style = sanitize_text(request_data.answer_style)
    user_goal = sanitize_text(request_data.user_goal)
    urgency_level = sanitize_text(request_data.urgency_level)
    output_format = sanitize_text(request_data.output_format)
    known_facts = sanitize_text(request_data.known_facts)
    verification_focus = sanitize_text(request_data.verification_focus)

    service = ComplianceAnswerService(db, tenant)
    response = await run_in_threadpool(
        service.answer,
        question=question,
        user_id=user_id,
        conversation_id=request_data.conversation_id,
        language=request_data.language,
        user_role=user_role,
        province=province,
        city=city,
        generation_id=request_data.generation_id,
        answer_style=answer_style,
        user_goal=user_goal,
        urgency_level=urgency_level,
        output_format=output_format,
        known_facts=known_facts,
        verification_focus=verification_focus,
    )

    response = _persist_chat_log(
        db,
        tenant,
        request,
        session_id=session_id,
        user_id=user_id,
        language=request_data.language,
        question=question,
        response=response,
        response_time=_elapsed_ms(request_start),
    )
    return ok(response.model_dump(), "回答生成成功")


@router.get("/chat-capabilities", response_model=dict)
def chat_capabilities(
    db: Session = Depends(get_db),
    header_tenant: Tenant = Depends(get_public_tenant),
):
    return ok(
        {
            "attachments": dify_attachment_capability(db, header_tenant),
        },
        "ok",
    )


@router.post("/chat-with-file", response_model=dict)
async def chat_with_file(
    request: Request,
    question: str = Form(...),
    session_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    tenant_code: Optional[str] = Form(None),
    language: str = Form("zh-CN"),
    conversation_id: Optional[str] = Form(None),
    generation_id: Optional[str] = Form(None),
    user_role: str = Form("employee"),
    province: str = Form("陕西省"),
    city: str = Form("西安市"),
    answer_style: Optional[str] = Form(None),
    user_goal: Optional[str] = Form(None),
    urgency_level: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
    known_facts: Optional[str] = Form(None),
    verification_focus: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    header_tenant: Tenant = Depends(get_public_tenant),
):
    request_start = time.perf_counter()
    if not question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    if not file.filename:
        raise HTTPException(status_code=400, detail="请上传文件")

    size = getattr(file, "size", None)
    if size is not None and size > settings.max_upload_bytes:
        await file.close()
        raise HTTPException(status_code=413, detail="上传文件过大")

    tenant = await _resolve_tenant(tenant_code, header_tenant, db)
    session_id = session_id or str(uuid.uuid4())
    user_id = sanitize_text(user_id) or "anonymous"
    question = sanitize_text(question) or ""
    user_role = sanitize_text(user_role) or "employee"
    province = sanitize_text(province) or "陕西省"
    city = sanitize_text(city) or "西安市"
    answer_style = sanitize_text(answer_style)
    user_goal = sanitize_text(user_goal)
    urgency_level = sanitize_text(urgency_level)
    output_format = sanitize_text(output_format)
    known_facts = sanitize_text(known_facts)
    verification_focus = sanitize_text(verification_focus)

    service = ComplianceAnswerService(db, tenant)
    try:
        response = await run_in_threadpool(
            service.answer,
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            language=language,
            user_role=user_role,
            province=province,
            city=city,
            attachment=ChatAttachment(
                filename=file.filename,
                content_type=file.content_type or "application/octet-stream",
                file=file.file,
            ),
            generation_id=generation_id,
            answer_style=answer_style,
            user_goal=user_goal,
            urgency_level=urgency_level,
            output_format=output_format,
            known_facts=known_facts,
            verification_focus=verification_focus,
        )
    finally:
        await file.close()

    response = _persist_chat_log(
        db,
        tenant,
        request,
        session_id=session_id,
        user_id=user_id,
        language=language,
        question=question,
        response=response,
        response_time=_elapsed_ms(request_start),
    )
    return ok(response.model_dump(), "回答生成成功")


@router.post("/chat/stop", response_model=dict)
async def stop_chat_generation(
    request_data: ChatStopRequest,
    db: Session = Depends(get_db),
    header_tenant: Tenant = Depends(get_public_tenant),
):
    await _resolve_tenant(request_data.tenant_code, header_tenant, db)
    stopped = ComplianceAnswerService.stop_generation(request_data.generation_id)
    return ok({"stopped": stopped}, "停止生成请求已处理")


@router.get("/history", response_model=dict)
async def get_history(
    user_id: str = "anonymous",
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    all_items: bool = False,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
):
    page, page_size = normalize_pagination(page, page_size)
    query = _history_query(db, tenant, user_id, keyword, status, provider)
    total = query.count()
    ordered = query.order_by(ChatLog.created_at.desc(), ChatLog.id.desc())
    logs = ordered.all() if all_items else ordered.offset((page - 1) * page_size).limit(page_size).all()
    data = HistoryResponse(total=total, page=page, page_size=page_size, list=logs)
    return ok(data.model_dump(), "历史记录获取成功")


@router.get("/history/export")
async def export_history(
    user_id: str = "anonymous",
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    ids: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
):
    query = _history_query(db, tenant, user_id, keyword, status, provider)
    parsed_ids = _parse_ids(ids)
    if parsed_ids:
        query = query.filter(ChatLog.id.in_(parsed_ids))
    logs = query.order_by(ChatLog.created_at.desc(), ChatLog.id.desc()).all()
    rows = [_serialize_history_item(item) for item in logs]
    return _csv_text_response("history.csv", rows, HISTORY_EXPORT_FIELDS)


@router.delete("/history")
async def clear_history(
    user_id: str = "anonymous",
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
):
    db.query(ChatLog).filter(ChatLog.tenant_id == tenant.id, ChatLog.user_id == sanitize_text(user_id)).delete()
    db.commit()
    return ok(message="历史记录已清空")


@router.get("/recommended-questions")
async def get_recommended_questions(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(get_public_tenant),
):
    data = [
        {"id": "kb-1", "question": "新员工入职后多久要办理社保？", "category": "社保", "risk_level": "medium"},
        {"id": "kb-2", "question": "试用期工资可以低于最低工资吗？", "category": "工资", "risk_level": "high"},
        {"id": "kb-3", "question": "陕西产假和护理假分别是多少天？", "category": "假期", "risk_level": "medium"},
        {"id": "kb-4", "question": "劳动仲裁时效是多久？", "category": "仲裁", "risk_level": "high"},
        {"id": "kb-5", "question": "员工自愿放弃社保可以吗？", "category": "社保", "risk_level": "high"},
        {"id": "kb-6", "question": "知识库材料包含身份证号时应该如何脱敏？", "category": "数据安全", "risk_level": "high"},
    ]
    return ok(data)


@router.get("/tenant-public")
async def get_tenant_public(tenant: Tenant = Depends(get_public_tenant)):
    return ok(
        {
            "id": tenant.id,
            "code": tenant.code,
            "name": tenant.name,
            "region": tenant.region,
            "industry": tenant.industry,
        }
    )
