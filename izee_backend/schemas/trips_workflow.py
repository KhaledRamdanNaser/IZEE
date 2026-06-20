from pydantic import BaseModel
from typing import Optional, List

class RegionCreate(BaseModel):
    region_id: Optional[str] = None
    region_name: str
    description: Optional[str] = None
    active: Optional[bool] = True
    route_ids: Optional[List[str]] = None

class RouteItem(BaseModel):
    route_id: str
    route_name: Optional[str] = None
    mode: Optional[str] = "Bus"

class RoutesMappingRequest(BaseModel):
    routes: List[RouteItem]

class SupervisorsMappingRequest(BaseModel):
    supervisors: List[str]

class VehiclesMappingRequest(BaseModel):
    vehicles: List[str]

class AssignmentCreateRequest(BaseModel):
    region_id: str
    driver_id: str
    vehicle_id: Optional[str] = None
    route_id: str
    service_date: str
    planned_start_time: str
    planned_end_time: str
    notes: Optional[str] = None
    trip_id: Optional[str] = None
    supervisor_id: Optional[str] = None
    status: Optional[str] = "scheduled"

class AssignmentUpdateRequest(BaseModel):
    region_id: Optional[str] = None
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    route_id: Optional[str] = None
    service_date: Optional[str] = None
    planned_start_time: Optional[str] = None
    planned_end_time: Optional[str] = None
    notes: Optional[str] = None
    trip_id: Optional[str] = None
    status: Optional[str] = None


class DriversMappingRequest(BaseModel):
    drivers: List[str]

