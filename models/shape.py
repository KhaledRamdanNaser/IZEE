from sqlalchemy import Column, String, Float, Integer
from database.connection import Base

class Shape(Base):
    __tablename__ = "shape"

    shape_id = Column(String, primary_key=True)
    lat = Column(Float, primary_key=True)
    lon = Column(Float, primary_key=True)
    sequence = Column(Integer)