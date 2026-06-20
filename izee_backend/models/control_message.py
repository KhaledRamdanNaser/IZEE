from sqlalchemy import Column, String, DateTime, JSON, Boolean
from database.connection import Base
import datetime
import uuid


class ControlMessage(Base):
    __tablename__ = "control_messages"

    message_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_type = Column(String, nullable=False, default="all_drivers")
    recipient_id = Column(String, nullable=True)
    sender = Column(String, nullable=False, default="Control Center")
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    priority = Column(String, nullable=False, default="normal")
    status = Column(String, nullable=False, default="sent")
    read = Column(Boolean, nullable=False, default=False)
    source = Column(String, nullable=False, default="control_center")
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)
