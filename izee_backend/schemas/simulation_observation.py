from pydantic import BaseModel
from datetime import datetime


class SimulationObservationRequest(BaseModel):

    vehicle_id: str

    route_id: str
    direction: int

    timestamp: datetime

    location: dict

    speed_kmh: float
    bearing: float

    day_of_week: str
    day_number: int
    time_period: str

    simulation_seed: int