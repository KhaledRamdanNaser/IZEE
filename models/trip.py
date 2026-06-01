from sqlalchemy import Column, Integer, String, ForeignKey
from database.connection import Base

class Trip(Base):
    __tablename__ = "trip"

    trip_id = Column(String, primary_key=True)
    route_id = Column(String, ForeignKey("route.route_id"))
    direction_id = Column(Integer)