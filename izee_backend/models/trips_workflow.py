from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from database.connection import Base
import datetime

class Region(Base):
    __tablename__ = "regions"

    region_id = Column(String, primary_key=True)
    region_name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class SupervisorRegion(Base):
    __tablename__ = "supervisor_regions"

    supervisor_id = Column(String, primary_key=True)
    region_id = Column(String, ForeignKey("regions.region_id", ondelete="CASCADE"), primary_key=True)


class RegionRoute(Base):
    __tablename__ = "region_routes"

    region_id = Column(String, ForeignKey("regions.region_id", ondelete="CASCADE"), primary_key=True)
    route_id = Column(String, primary_key=True)
    route_name = Column(String, nullable=True)
    mode = Column(String, nullable=True)


class RegionVehicle(Base):
    __tablename__ = "region_vehicles"

    region_id = Column(String, ForeignKey("regions.region_id", ondelete="CASCADE"), primary_key=True)
    vehicle_id = Column(String, primary_key=True)


class DriverAssignment(Base):
    __tablename__ = "driver_assignments"

    assignment_id = Column(String, primary_key=True)
    supervisor_id = Column(String, nullable=False)
    region_id = Column(String, ForeignKey("regions.region_id"), nullable=False)
    driver_id = Column(String, nullable=False)
    vehicle_id = Column(String, nullable=False)
    route_id = Column(String, nullable=False)
    route_name = Column(String, nullable=True)
    trip_id = Column(String, nullable=False)
    service_date = Column(String, nullable=False)
    planned_start_time = Column(String, nullable=False)
    planned_end_time = Column(String, nullable=False)
    actual_start_time = Column(String, nullable=True)
    actual_end_time = Column(String, nullable=True)
    status = Column(String, nullable=False, default="scheduled")
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # Driver, Supervisor, Operator
    status = Column(String, default="active")
    last_active = Column(String, default="Now")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class RegionDriverMapping(Base):
    __tablename__ = "region_driver_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_id = Column(String, ForeignKey("regions.region_id", ondelete="CASCADE"), nullable=False)
    driver_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class PassengerFavorite(Base):
    __tablename__ = "passenger_favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    passenger_id = Column(String, nullable=False, index=True)
    route_id = Column(String, nullable=False)
    route_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class PassengerTripHistory(Base):
    __tablename__ = "passenger_trip_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    passenger_id = Column(String, nullable=False, index=True)
    route_id = Column(String, nullable=False)
    route_name = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


