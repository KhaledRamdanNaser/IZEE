from sqlalchemy import Column, String, Float, Integer
from database.connection import Base

class WalkingTransfer(Base):
    __tablename__ = "walking_transfer"

    from_stop_id = Column(String, primary_key=True)
    to_stop_id = Column(String, primary_key=True)
    walk_type = Column(String, primary_key=True)  # normal_transfer / emergency_access

    distance_meters = Column(Float, nullable=False)
    walking_time = Column(Integer, nullable=False)
