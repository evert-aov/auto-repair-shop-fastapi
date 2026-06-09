import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("report_templates.id", ondelete="CASCADE"), nullable=False)
    frequency = Column(String(50), nullable=False)  # daily, weekly, monthly
    hour = Column(String(5), nullable=False)        # "08:00"
    email = Column(String(255), nullable=False)
    format = Column(String(10), nullable=False, default="pdf")  # pdf, excel, csv
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
