from pydantic import BaseModel, model_validator
from typing import Optional
from datetime import datetime

class Location(BaseModel):
    lat: float
    lon: float

class VehicleLocationRequest(BaseModel):
    vehicle_id: Optional[str] = None
    route_id: str
    direction: int
    timestamp: datetime

    location: Optional[Location] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

    speed: Optional[float] = None
    bearing: Optional[float] = None

    @model_validator(mode="after")
    def normalize_location(self):

        # Case 1: location provided
        if self.location is not None:
            self.lat = self.location.lat
            self.lon = self.location.lon

        # Case 2: lat/lon provided
        elif self.lat is not None and self.lon is not None:
            self.location = Location(lat=self.lat, lon=self.lon)

        else:
            raise ValueError("Provide either location or lat/lon")

        return self