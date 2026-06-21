"""
Pydantic模型包
"""
from app.schemas.chat import ChatRequest, ChatResponse, SourceInfo, TaskInfo, HistoryItem, HistoryResponse
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate, FeedbackResponse
from app.schemas.source import SourceCreate, SourceUpdate, SourceResponse
from app.schemas.admin import (
    AdminLogin,
    AdminToken,
    AdminInfo,
    StatisticsResponse,
    TenantCreate,
    TenantUpdate,
    TenantResponse,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "SourceInfo",
    "TaskInfo",
    "HistoryItem",
    "HistoryResponse",
    "FeedbackCreate",
    "FeedbackUpdate",
    "FeedbackResponse",
    "SourceCreate",
    "SourceUpdate",
    "SourceResponse",
    "AdminLogin",
    "AdminToken",
    "AdminInfo",
    "StatisticsResponse",
    "TenantCreate",
    "TenantUpdate",
    "TenantResponse",
]
