from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean
from database.connection import Base


class DriverRouteAssignment(Base):
    __tablename__ = "driver_route_assignments"

    assignment_id = Column(String, primary_key=True, index=True)
    vehicle_id = Column(String, index=True, nullable=True)
    driver_id = Column(String, nullable=True)
    route_id = Column(String, index=True, nullable=False)
    route_name = Column(String, nullable=True)
    origin = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    current_stop_sequence = Column(Integer, default=1)
    progress_percent = Column(Float, default=0.0)
    status = Column(String, default="scheduled")
    trip_id = Column(String, nullable=True)
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)
    service_date = Column(String, nullable=True)
    assigned_by = Column(String, nullable=True)
    assigned_by_supervisor_id = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    region_id = Column(String, nullable=True)
    actual_start_time = Column(String, nullable=True)
    actual_end_time = Column(String, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_reason = Column(String, nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)


class DriverRouteStop(Base):
    __tablename__ = "driver_route_stops"

    stop_id = Column(String, primary_key=True, index=True)
    route_id = Column(String, index=True, nullable=False)
    stop_sequence = Column(Integer, nullable=False)
    stop_name = Column(String, nullable=False)
    scheduled_time = Column(String, nullable=True)
    distance_km = Column(Float, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
