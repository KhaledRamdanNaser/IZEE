from sqlalchemy import Column, String, Integer, ForeignKey
from database.connection import Base

class StopTime(Base):
    __tablename__ = "stop_time"

    trip_id = Column(String, ForeignKey("trip.trip_id"), primary_key=True)
    stop_id = Column(String, ForeignKey("stop.stop_id"), primary_key=True)

    stop_sequence = Column(Integer)