from pydantic import BaseModel

class VehicleLocationRequest(BaseModel):
    vehicle_id: str
    lat: float
    lon: float