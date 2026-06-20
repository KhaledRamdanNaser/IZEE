from dataclasses import dataclass
from typing import List, Dict

@dataclass
class StopTime:
    stop_id: int
    arrival: int      # Seconds from midnight
    departure: int
    segment_id: str

@dataclass
class Trip:
    id: str
    route_id: str
    stop_times: List[StopTime]

@dataclass
class Route:
    id: str
    stops: List[int]
    trips: List[Trip]

class TransitGraph:
    def __init__(self):
        self.stops: Dict[int, dict] = {} # Metadata like lat/lon
        self.routes: Dict[str, Route] = {}
        self.stop_to_routes: Dict[int, List[str]] = {}