# --- KHALED EDIT START ---
from sqlalchemy import Column, String, Integer, Float, DateTime, UniqueConstraint
from database.connection import Base

class SegmentStatistics(Base):
    __tablename__ = "segment_statistics"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    segment_id         = Column(String, nullable=False)
    route_id           = Column(String, nullable=False)
    direction          = Column(Integer, nullable=False)
    day_type           = Column(String, nullable=False)
    time_period        = Column(String, nullable=False)
    avg_travel_time    = Column(Float, nullable=True)
    median_travel_time = Column(Float, nullable=True)
    std_travel_time    = Column(Float, nullable=True)
    sample_count       = Column(Integer, nullable=True)
    last_updated       = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "segment_id",
            "route_id",
            "direction",
            "day_type",
            "time_period",
            name="uq_segment_statistics"
        ),
    )
# --- KHALED EDIT END ---