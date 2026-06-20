from sqlalchemy import Column, String, Boolean, Float, DateTime, ForeignKey, Integer
from datetime import datetime
from database.connection import Base

class Region(Base):
    __tablename__ = "regions"

    region_id = Column(String, primary_key=True, index=True)
    region_name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    center_lat = Column(Float, nullable=True)
    center_lon = Column(Float, nullable=True)
    boundary_geojson = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class SupervisorRegion(Base):
    __tablename__ = "supervisor_regions"

    supervisor_id = Column(String, primary_key=True, index=True)
    region_id = Column(String, primary_key=True, index=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)

class RegionRoute(Base):
    __tablename__ = "region_routes"

    region_id = Column(String, primary_key=True, index=True)
    route_id = Column(String, primary_key=True, index=True)
    route_name = Column(String, nullable=True)
    mode = Column(String, nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)

class RegionVehicle(Base):
    __tablename__ = "region_vehicles"

    region_id = Column(String, primary_key=True, index=True)
    vehicle_id = Column(String, primary_key=True, index=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)

class OperationalRoute(Base):
    __tablename__ = "operational_routes"

    route_id = Column(String, primary_key=True, index=True)
    route_short_name = Column(String, nullable=True)
    route_long_name = Column(String, nullable=True)
    route_type = Column(Integer, nullable=True)
    mode = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

class RegionRouteMapping(Base):
    __tablename__ = "region_route_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_id = Column(String, ForeignKey("regions.region_id", ondelete="CASCADE"), nullable=False)
    route_id = Column(String, ForeignKey("operational_routes.route_id", ondelete="CASCADE"), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RegionDriverMapping(Base):
    __tablename__ = "region_driver_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_id = Column(String, ForeignKey("regions.region_id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(String, nullable=False, index=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
