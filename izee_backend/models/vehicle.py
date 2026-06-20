from sqlalchemy import Column, String, Float, Integer, DateTime
from database.connection import Base
import datetime

class VehicleLiveState(Base):
    __tablename__ = "vehicle_live_state"

    vehicle_id = Column(String, primary_key=True, index=True)
    lat = Column(Float)
    lon = Column(Float)
    eta = Column(Integer)
    last_update = Column(DateTime, default=datetime.datetime.utcnow)