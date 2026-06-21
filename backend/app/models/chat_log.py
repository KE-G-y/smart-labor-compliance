"""问答记录模型。"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ChatLog(Base):
    """问答记录表"""
    __tablename__ = "slc_chat_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("slc_tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    conversation_id = Column(String(128), nullable=True, index=True)
    language = Column(String(12), default="zh-CN", nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    sources = Column(JSON, nullable=True)
    related_tasks = Column(JSON, nullable=True)
    provider = Column(String(30), default="kb_no_match", nullable=False)
    risk_level = Column(String(20), default="medium", nullable=False)
    evaluation = Column(JSON, nullable=True)
    response_time = Column(Integer, nullable=True)
    status = Column(String(20), default="success")
    client_ip_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    tenant = relationship("Tenant", back_populates="chat_logs")

    def __repr__(self):
        return f"<ChatLog {self.id}: {self.question[:30]}>"
