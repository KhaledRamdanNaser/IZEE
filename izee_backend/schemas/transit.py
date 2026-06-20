from pydantic import BaseModel, model_validator
from typing import Optional
from datetime import datetime

class Location(BaseModel):
    lat: float
    lon: float

class VehicleLocationRequest(BaseModel):
    vehicle_id: Optional[str] = None
    route_id: Optional[str] = None
    direction: Optional[int] = 0
    timestamp: datetime

    location: Optional[Location] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    lng: Optional[float] = None

    speed: Optional[float] = None
    bearing: Optional[float] = None
    heading: Optional[float] = None

    assignment_id: Optional[str] = None
    driver_id: Optional[str] = None
    trip_id: Optional[str] = None

    @model_validator(mode="after")
    def normalize_location(self):

        # Case 1: location provided
        if self.location is not None:
            self.lat = self.location.lat
            self.lon = self.location.lon

        # Case 2: lat/lon provided
        elif self.lat is not None and self.lon is not None:
            self.location = Location(lat=self.lat, lon=self.lon)

        # Case 3: lat/lng provided by mobile map APIs
        elif self.lat is not None and self.lng is not None:
            self.lon = self.lng
            self.location = Location(lat=self.lat, lon=self.lng)

        else:
            raise ValueError("Provide either location or lat/lon")

        if self.bearing is None and self.heading is not None:
            self.bearing = self.heading

        return self
