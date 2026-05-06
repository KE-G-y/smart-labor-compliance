"""系统配置模型（用于存储可动态修改的全局配置）。"""
from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.sql import func

from app.database import Base


class SystemConfig(Base):
    """系统配置表，存储可动态修改的全局配置项。"""

    __tablename__ = "slc_system_config"

    id = Column(String(64), primary_key=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<SystemConfig {self.id}>"