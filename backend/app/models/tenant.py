"""租户模型。"""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Tenant(Base):
    """企业租户。"""

    __tablename__ = "slc_tenants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    industry = Column(String(80), nullable=True)
    region = Column(String(80), default="陕西", nullable=False)
    contact_name = Column(String(80), nullable=True)
    contact_email = Column(String(120), nullable=True)
    contact_phone = Column(String(40), nullable=True)
    status = Column(String(20), default="active", nullable=False)
    data_scope = Column(String(30), default="tenant", nullable=False)
    dify_api_key = Column(Text, nullable=True)
    dify_app_id = Column(String(120), nullable=True)
    ragflow_dataset_id = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    is_demo = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    admins = relationship("Admin", back_populates="tenant", cascade="all, delete-orphan")
    chat_logs = relationship("ChatLog", back_populates="tenant", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_packages = relationship("KnowledgePackage", back_populates="tenant", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="tenant", cascade="all, delete-orphan")
    test_questions = relationship("TestQuestion", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant {self.id}: {self.code}>"
