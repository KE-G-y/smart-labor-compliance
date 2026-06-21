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

    query_strategy: Optional[str] = None
    dify_base_url: Optional[str] = None
    dify_api_key: Optional[str] = None
    dify_timeout_seconds: Optional[int] = None
    langchain_base_url: Optional[str] = None
    langchain_api_key: Optional[str] = None
    langchain_model: Optional[str] = None
    langchain_embedding_model: Optional[str] = None
    langchain_temperature: Optional[float] = None
    langchain_timeout_seconds: Optional[int] = None
    milvus_uri: Optional[str] = None
    milvus_token: Optional[str] = None
    milvus_collection: Optional[str] = None
    active_vector_version_id: Optional[str] = None
    vector_search_mode: Optional[str] = None
    vector_top_k: Optional[int] = None
    vector_chunk_size: Optional[int] = None
    vector_chunk_overlap: Optional[int] = None
    local_embedding_enabled: Optional[bool] = None
    local_embedding_model_path: Optional[str] = None
    local_reranker_enabled: Optional[bool] = None
    local_reranker_model_path: Optional[str] = None
    local_fallback_bert_model_path: Optional[str] = None
    ragflow_base_url: Optional[str] = None
    ragflow_web_url: Optional[str] = None
    ragflow_api_key: Optional[str] = None
    ragflow_timeout_seconds: Optional[int] = None


class SystemConfigResponse(BaseModel):
    """系统配置响应（返回配置的 key，不返回敏感 value）。"""

    query_strategy: str = "langchain_first"
    dify_base_url: Optional[str] = None
    dify_api_key_configured: bool = False
    dify_timeout_seconds: int = 30
    langchain_base_url: Optional[str] = None
    langchain_api_key_configured: bool = False
    langchain_model: str = "gpt-4o-mini"
    langchain_embedding_model: str = "bge-m3"
    langchain_temperature: float = 0.2
    langchain_timeout_seconds: int = 45
    milvus_uri: Optional[str] = None
    milvus_token_configured: bool = False
    milvus_collection: str = "slc_compliance_docs"
    active_vector_version_id: Optional[str] = None
    vector_search_mode: str = "hybrid"
    vector_top_k: int = 4
    vector_chunk_size: int = 500
    vector_chunk_overlap: int = 50
    local_embedding_enabled: bool = True
    local_embedding_model_path: str = "models/bge-m3"
    local_reranker_enabled: bool = True
    local_reranker_model_path: str = "models/bge-reranker-large"
    local_fallback_bert_model_path: str = "models/bert-base-chinese"
    ragflow_base_url: Optional[str] = None
    ragflow_web_url: Optional[str] = None
    ragflow_api_key_configured: bool = False
    ragflow_timeout_seconds: int = 10


class VectorVersionActivateRequest(BaseModel):
    """激活向量库版本请求。"""

    tenant_id: Optional[int] = None


class VectorVersionArchiveRequest(BaseModel):
    """归档向量库版本请求。"""

    tenant_id: Optional[int] = None


class VectorVersionResponse(BaseModel):
    """向量库版本响应。"""

    id: int
    tenant_id: int
    tenant_code: Optional[str] = None
    tenant_name: Optional[str] = None
    version: str
    collection_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    manifest_path: Optional[str] = None
    manifest_sha256: Optional[str] = None
    categories: Optional[list] = None
    embedding_model: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    document_count: int = 0
    indexed_count: int = 0
    failed_count: int = 0
    chunk_count: int = 0
    status: str
    is_active: bool
    build_started_at: Optional[datetime] = None
    build_finished_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    activated_by: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
