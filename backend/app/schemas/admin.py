"""管理员与租户相关 Pydantic 模型。"""
from typing import Optional

from pydantic import BaseModel, Field
from datetime import datetime


class AdminLogin(BaseModel):
    """管理员登录请求"""
    username: str
    password: str
    tenant_code: Optional[str] = None


class AdminCreate(BaseModel):
    """管理员创建请求"""
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    role: str = "operator"
    display_name: Optional[str] = None
    email: Optional[str] = None
    tenant_id: Optional[int] = None


class AdminUpdate(BaseModel):
    """管理员更新请求"""
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    role: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None


class AdminToken(BaseModel):
    """管理员令牌响应"""
    access_token: str
    token_type: str = "bearer"
    admin_id: int
    username: str
    role: str
    role_label: str
    permissions: list[str]
    tenant_id: Optional[int]
    tenant_code: Optional[str]
    tenant_name: Optional[str]


class AdminInfo(BaseModel):
    """管理员信息"""
    id: int
    tenant_id: Optional[int]
    username: str
    role: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class StatisticsResponse(BaseModel):
    """统计数据响应"""
    total_questions: int
    today_questions: int
    total_feedbacks: int
    pending_feedbacks: int
    total_faqs: int
    total_sources: int
    total_tenants: int
    helpful_rate: int
    avg_response_time: int
    top_questions: list[dict]


class TenantCreate(BaseModel):
    """租户创建请求。"""

    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    industry: Optional[str] = None
    region: str = "陕西"
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None
    admin_username: Optional[str] = Field(default=None, min_length=2, max_length=50)
    admin_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class TenantUpdate(BaseModel):
    """租户更新请求。"""

    name: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    dify_api_key: Optional[str] = None
    dify_app_id: Optional[str] = None
    ragflow_dataset_id: Optional[str] = None


class TenantResponse(BaseModel):
    """租户响应。"""

    id: int
    code: str
    name: str
    industry: Optional[str] = None
    region: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    """系统配置更新请求。"""

    dify_base_url: Optional[str] = None
    dify_api_key: Optional[str] = None
    dify_timeout_seconds: Optional[int] = None
    ragflow_base_url: Optional[str] = None
    ragflow_web_url: Optional[str] = None
    ragflow_api_key: Optional[str] = None
    ragflow_timeout_seconds: Optional[int] = None


class SystemConfigResponse(BaseModel):
    """系统配置响应（返回配置的 key，不返回敏感 value）。"""

    dify_base_url: Optional[str] = None
    dify_api_key_configured: bool = False
    dify_timeout_seconds: int = 30
    ragflow_base_url: Optional[str] = None
    ragflow_web_url: Optional[str] = None
    ragflow_api_key_configured: bool = False
    ragflow_timeout_seconds: int = 10
