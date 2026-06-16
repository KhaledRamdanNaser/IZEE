from sqlalchemy import Column, String, Integer, Boolean, JSON
from database.connection import Base

class TransitEvent(Base):
    __tablename__ = "transit_events"

    event_id = Column(String, primary_key=True, index=True)

    event_type = Column(String, index=True)

    vehicle_id = Column(String, index=True)
    route_id = Column(String, index=True)  # keep String if your routes are strings like "CTA_M_112"

    timestamp = Column(String, index=True)  # ISO8601 OK for now

    # Optional IDs — keep as String if your stop_ids are strings
    stop_id = Column(String, nullable=True)
    from_stop_id = Column(String, nullable=True)
    to_stop_id = Column(String, nullable=True)
    segment_id = Column(String, nullable=True)

    # ⚠️ was Float before — should be Integer
    stop_sequence = Column(Integer, nullable=True)

    # Flexible metrics
    metrics = Column(JSON)

    confidence = Column(String)
    source = Column(String)
    simulation_flag = Column(Boolean)

    # --- KHALED EDIT START ---
    day_of_week = Column(String, nullable=True)
    time_period  = Column(String, nullable=True)
    direction    = Column(Integer, nullable=True)
    # --- KHALED EDIT END ---