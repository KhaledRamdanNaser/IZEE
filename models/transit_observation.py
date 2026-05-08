from sqlalchemy import Column, String, Float, DateTime, Boolean, JSON, UniqueConstraint
from database.connection import Base
import datetime
import uuid
from enums.transit import SourceEnum, TrustLevelEnum

from sqlalchemy import Enum as SQLEnum

class TransitObservation(Base):
    __tablename__ = "transit_observations"

    __table_args__ = (
        UniqueConstraint("vehicle_id", "timestamp", name="uq_vehicle_timestamp"),
    )

    observation_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    vehicle_id = Column(String, nullable=True)

    timestamp = Column(DateTime, nullable=False)

    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    speed = Column(Float, nullable=True)
    bearing = Column(Float, nullable=True)

    source = Column(SQLEnum(SourceEnum, name="source_enum"), nullable=False)
    simulation_flag = Column(Boolean, default=False)
    trust_level = Column(SQLEnum(TrustLevelEnum, name="trust_level_enum"), nullable=False)

    raw_payload = Column(JSON, nullable=True)

    ingested_at = Column(DateTime, default=datetime.datetime.utcnow)