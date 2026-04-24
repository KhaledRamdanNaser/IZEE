from sqlalchemy import Column, String, Float, Integer, Boolean
from database.connection import Base

class VehicleLiveState(Base):
    __tablename__ = "vehicle_live_state"

    vehicle_id = Column(String, primary_key=True, index=True)
    route_id = Column(String)

    timestamp = Column(String)

    matched_lat = Column(Float)
    matched_lon = Column(Float)

    current_stop_id = Column(String, nullable=True)
    next_stop_id = Column(String)

    stop_sequence = Column(Integer, nullable=True)

    segment_id = Column(String)
    segment_progress = Column(Float)
    progress = Column(Float)

    distance_to_next_stop = Column(Float)

    speed = Column(Float)
    direction = Column(String)

    movement = Column(String)
    movement_state = Column(String)

    current_delay = Column(Float)
    confidence = Column(String)

    source = Column(String)
    simulation_flag = Column(Boolean)