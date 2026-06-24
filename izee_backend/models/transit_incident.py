from sqlalchemy import Column, String, Float, DateTime, JSON, Boolean
from database.connection import Base
import datetime
import uuid


class TransitIncident(Base):
    __tablename__ = "transit_incidents"

    incident_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    category = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="warning")
    status = Column(String, nullable=False, default="new")
    transmitted_to_control = Column(Boolean, nullable=False, default=False)
    passenger_id = Column(String, nullable=True)

    vehicle_id = Column(String, nullable=True)
    route_id = Column(String, nullable=True)
    driver_name = Column(String, nullable=True)

    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    location_label = Column(String, nullable=True)

    details = Column(String, nullable=True)
    source = Column(String, nullable=False, default="driver_app")
    raw_payload = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class TransitNotification(Base):
    __tablename__ = "transit_notifications"

    notification_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    passenger_id = Column(String, nullable=False, default="local-passenger")
    title = Column(String, nullable=False)
    body = Column(String, nullable=False)
    unread = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
