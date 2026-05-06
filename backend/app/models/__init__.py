"""数据模型包。"""
from app.models.tenant import Tenant
from app.models.chat_log import ChatLog
from app.models.feedback import Feedback
from app.models.faq import FAQ
from app.models.source import Source
from app.models.knowledge_package import KnowledgePackage
from app.models.admin import Admin
from app.models.test_question import TestQuestion
from app.models.system_config import SystemConfig

__all__ = [
    "Tenant",
    "ChatLog",
    "Feedback",
    "FAQ",
    "Source",
    "KnowledgePackage",
    "Admin",
    "TestQuestion",
    "SystemConfig",
]
