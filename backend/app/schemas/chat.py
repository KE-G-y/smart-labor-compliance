"""问答相关 Pydantic 模型。"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    """问答请求"""
    question: str = Field(min_length=1, max_length=3000)
    generation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    tenant_code: Optional[str] = None
    language: str = "zh-CN"
    conversation_id: Optional[str] = None
    user_role: str = "employee"
    province: str = "陕西省"
    city: str = "西安市"
    answer_style: Optional[str] = Field(default=None, max_length=600)
    user_goal: Optional[str] = Field(default=None, max_length=160)
    urgency_level: Optional[str] = Field(default=None, max_length=80)
    output_format: Optional[str] = Field(default=None, max_length=120)
    known_facts: Optional[str] = Field(default=None, max_length=1000)
    verification_focus: Optional[str] = Field(default=None, max_length=600)


class ChatStopRequest(BaseModel):
    """停止生成请求"""

    generation_id: str = Field(min_length=1, max_length=120)
    user_id: Optional[str] = None
    tenant_code: Optional[str] = None


class SourceInfo(BaseModel):
    """来源信息"""
    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None


class TaskInfo(BaseModel):
    """办事路径信息"""
    title: str
    steps: List[str]
    url: Optional[str] = None


class ChatResponse(BaseModel):
    """问答响应"""
    answer: str
    sources: Optional[List[SourceInfo]] = None
    related_tasks: Optional[List[TaskInfo]] = None
    response_time: int
    conversation_id: Optional[str] = None
    question_id: Optional[int] = None
    provider: str = "local_faq"
    risk_level: str = "medium"
    suggestions: List[str] = []
    disclaimer: Optional[str] = None


class HistoryItem(BaseModel):
    """历史记录项"""
    id: int
    tenant_id: int
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    language: str = "zh-CN"
    question: str
    answer: Optional[str] = None
    sources: Optional[List[dict]] = None
    related_tasks: Optional[List[dict]] = None
    provider: str
    risk_level: str = "medium"
    response_time: Optional[int]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    """历史记录响应"""
    total: int
    page: int = 1
    page_size: int = 20
    list: List[HistoryItem]
