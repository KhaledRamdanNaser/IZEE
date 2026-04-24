from sqlalchemy import Column, String, ForeignKey
from database.connection import Base

class Route(Base):
    __tablename__ = "route"

    route_id = Column(String, primary_key=True)
    route_name = Column(String)

    agency_id = Column(String, ForeignKey("agency.agency_id"))