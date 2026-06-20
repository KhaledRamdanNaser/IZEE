from enum import Enum

class SourceEnum(str, Enum):
    driver_app = "driver_app"
    simulated = "simulated"
    crowdsensed = "crowdsensed"
    avl = "avl"


class TrustLevelEnum(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"