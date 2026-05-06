"""路由依赖：认证、租户解析与分页约束。"""
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db, settings
from app.models import Admin, Tenant
from app.security import decode_token, role_label, role_permissions


async def get_current_admin(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="未授权")

    try:
        scheme, token = authorization.split()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="无效的授权头") from exc

    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="无效的认证方案")

    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="令牌无效或已过期")

    admin = db.query(Admin).filter(Admin.id == int(payload["sub"]), Admin.is_active.is_(True)).first()
    if not admin:
        raise HTTPException(status_code=401, detail="管理员不存在或已停用")

    tenant = admin.tenant
    return {
        "id": admin.id,
        "username": admin.username,
        "display_name": admin.display_name,
        "role": admin.role,
        "role_label": role_label(admin.role),
        "permissions": role_permissions(admin.role),
        "tenant_id": admin.tenant_id,
        "tenant_code": tenant.code if tenant else None,
        "tenant_name": tenant.name if tenant else None,
    }


def get_admin_tenant_filter(current_admin: dict, requested_tenant_id: Optional[int] = None) -> Optional[int]:
    """返回当前管理员可操作的 tenant_id。超级管理员可传 None 表示全部。"""
    if current_admin["role"] == "super_admin":
        return requested_tenant_id
    if requested_tenant_id and requested_tenant_id != current_admin.get("tenant_id"):
        raise HTTPException(status_code=403, detail="不能访问其他租户数据")
    tenant_id = current_admin.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="当前账号未绑定租户")
    return tenant_id


def get_public_tenant(
    tenant_code: Optional[str] = Header(default=None, alias="X-Tenant-Code"),
    db: Session = Depends(get_db),
) -> Tenant:
    code = tenant_code or settings.default_tenant_code
    tenant = db.query(Tenant).filter(Tenant.code == code, Tenant.status == "active").first()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在或已停用")
    return tenant


def normalize_pagination(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    return page, page_size


def order_by_newest(query, model):
    """Order list queries by newest created record first with a stable id tie-breaker."""
    order_columns = []
    created_at = getattr(model, "created_at", None)
    id_column = getattr(model, "id", None)
    if created_at is not None:
        order_columns.append(created_at.desc())
    if id_column is not None:
        order_columns.append(id_column.desc())
    return query.order_by(*order_columns) if order_columns else query
