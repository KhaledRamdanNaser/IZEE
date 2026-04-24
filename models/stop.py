from sqlalchemy import Column, String, Float
from database.connection import Base

class Stop(Base):
    __tablename__ = "stop"

    stop_id = Column(String, primary_key=True)
    name = Column(String)
    lat = Column(Float)
    lon = Column(Float)