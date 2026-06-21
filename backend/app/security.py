"""安全模块：JWT、密码哈希、角色权限与脱敏工具。"""
import hashlib
import hmac
import re
from datetime import datetime, timedelta
from typing import Iterable, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.database import SessionLocal, settings
from app.models import Admin, Tenant

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_LABELS = {
    "super_admin": "超级管理员",
    "tenant_admin": "租户管理员",
    "operator": "运营人员",
    "viewer": "只读人员",
}

ROLE_PERMISSIONS = {
    "super_admin": [
        "dashboard",
        "tenants",
        "admins",
        "logs",
        "feedbacks",
        "sources",
        "sources_import",
        "sources_export",
        "sources_batch",
        "vector_versions",
        "packages",
        "packages_import",
        "packages_export",
        "packages_batch",
        "test_questions",
        "settings",
        "system_config",
    ],
    "tenant_admin": [
        "dashboard",
        "admins",
        "logs",
        "feedbacks",
        "sources",
        "sources_import",
        "sources_export",
        "sources_batch",
        "vector_versions",
        "packages",
        "packages_import",
        "packages_export",
        "packages_batch",
        "test_questions",
    ],
    "operator": [
        "dashboard",
        "logs",
        "feedbacks",
        "sources",
        "sources_import",
        "sources_export",
        "sources_batch",
        "packages",
        "packages_import",
        "packages_export",
        "packages_batch",
        "test_questions",
    ],
    "viewer": ["dashboard", "logs"],
}

SUPER_ADMIN_ROLES = {"super_admin"}
TENANT_ADMIN_ROLES = {"super_admin", "tenant_admin"}

SENSITIVE_PATTERNS = [
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[身份证号已脱敏]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机号已脱敏]"),
    (re.compile(r"(?<!\d)\d{12,19}(?!\d)"), "[银行卡号已脱敏]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[邮箱已脱敏]"),
]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """解码令牌"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


def role_permissions(role: str) -> list[str]:
    return ROLE_PERMISSIONS.get(role, [])


def require_role(role: str, allowed_roles: Iterable[str]) -> None:
    if role not in allowed_roles:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="当前账号没有该操作权限")


def sanitize_text(text: Optional[str]) -> Optional[str]:
    """脱敏个人敏感信息，避免写入日志或知识库。"""
    if text is None:
        return None
    cleaned = text.strip()
    for pattern, replacement in SENSITIVE_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    digest = hmac.new(settings.jwt_secret_key.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def authenticate_admin(username: str, password: str, tenant_code: Optional[str] = None) -> Optional[dict]:
    """验证管理员"""
    db = SessionLocal()
    try:
        query = db.query(Admin).filter(Admin.username == username, Admin.is_active.is_(True))
        if tenant_code:
            query = query.join(Tenant).filter(Tenant.code == tenant_code)
        admin = query.order_by(Admin.id.asc()).first()
        if not admin:
            return None
        if not verify_password(password, admin.password_hash):
            return None
        admin.last_login_at = datetime.utcnow()
        db.commit()
        tenant = admin.tenant
        return {
            "id": admin.id,
            "username": admin.username,
            "role": admin.role,
            "tenant_id": admin.tenant_id,
            "tenant_code": tenant.code if tenant else None,
            "tenant_name": tenant.name if tenant else None,
        }
    finally:
        db.close()


def create_admin(
    username: str,
    password: str,
    role: str = "operator",
    tenant_id: Optional[int] = None,
    display_name: Optional[str] = None,
) -> bool:
    """创建管理员账号"""
    db = SessionLocal()
    try:
        # 检查是否已存在
        existing = db.query(Admin).filter(Admin.username == username, Admin.tenant_id == tenant_id).first()
        if existing:
            return False
        
        admin = Admin(
            username=username,
            password_hash=get_password_hash(password),
            role=role,
            tenant_id=tenant_id,
            display_name=display_name,
        )
        db.add(admin)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"创建管理员失败: {e}")
        return False
    finally:
        db.close()
