"""反馈路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_admin_tenant_filter, get_current_admin, get_public_tenant, normalize_pagination, order_by_newest
from app.models import ChatLog, Feedback, Tenant
from app.response import ok, page as page_response
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate
from app.security import sanitize_text

router = APIRouter(prefix="/api", tags=["反馈"])


def _require_permission(current_admin: dict, permission: str) -> None:
    if permission not in current_admin.get("permissions", []):
        raise HTTPException(status_code=403, detail="当前账号没有该操作权限")


@router.post("/feedback")
async def create_feedback(
    request: FeedbackCreate,
    db: Session = Depends(get_db),
    header_tenant: Tenant = Depends(get_public_tenant),
):
    tenant = header_tenant
    if request.tenant_code and request.tenant_code != tenant.code:
        tenant = db.query(Tenant).filter(Tenant.code == request.tenant_code, Tenant.status == "active").first()
        if not tenant:
            raise HTTPException(status_code=404, detail="租户不存在或已停用")

    if request.question_id:
        exists = db.query(ChatLog).filter(ChatLog.id == request.question_id, ChatLog.tenant_id == tenant.id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="问答记录不存在")

    feedback = Feedback(
        tenant_id=tenant.id,
        question_id=request.question_id,
        user_id=sanitize_text(request.user_id) or "anonymous",
        is_helpful=request.is_helpful,
        remark=sanitize_text(request.remark),
        status="pending",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return ok({"id": feedback.id}, "反馈提交成功")


@router.get("/admin/feedbacks")
async def get_feedbacks(
    tenant_id: int | None = None,
    status: str | None = None,
    is_helpful: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "feedbacks")
    page, page_size = normalize_pagination(page, page_size)
    allowed_tenant_id = get_admin_tenant_filter(current_admin, tenant_id)
    query = db.query(Feedback)
    if allowed_tenant_id:
        query = query.filter(Feedback.tenant_id == allowed_tenant_id)
    if status:
        query = query.filter(Feedback.status == status)
    if is_helpful is not None:
        query = query.filter(Feedback.is_helpful.is_(is_helpful))
    total = query.count()
    items = order_by_newest(query, Feedback).offset((page - 1) * page_size).limit(page_size).all()
    data = [
        {
            "id": item.id,
            "tenant_id": item.tenant_id,
            "tenant_name": item.tenant.name if item.tenant else "",
            "question_id": item.question_id,
            "question": item.chat_log.question if item.chat_log else "",
            "user_id": item.user_id,
            "is_helpful": item.is_helpful,
            "remark": item.remark,
            "status": item.status,
            "created_at": item.created_at,
        }
        for item in items
    ]
    return page_response(data, total, page, page_size)


@router.put("/admin/feedbacks/{feedback_id}")
async def update_feedback(
    feedback_id: int,
    request: FeedbackUpdate,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    _require_permission(current_admin, "feedbacks")
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    get_admin_tenant_filter(current_admin, feedback.tenant_id)
    if request.status:
        if request.status not in {"pending", "processing", "resolved", "ignored"}:
            raise HTTPException(status_code=400, detail="无效的反馈状态")
        feedback.status = request.status
    db.commit()
    db.refresh(feedback)
    return ok(message="反馈更新成功")
