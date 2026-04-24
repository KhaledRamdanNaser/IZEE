from sqlalchemy import Column, String
from database.connection import Base

class Agency(Base):
    __tablename__ = "agency"

    agency_id = Column(String, primary_key=True)
    name = Column(String)