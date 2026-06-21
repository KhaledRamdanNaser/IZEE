from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime
)

from database.connection import Base

import datetime
import uuid


class VehicleStateHistory(Base):

    __tablename__ = "vehicle_state_history"


    state_id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )


    vehicle_id = Column(
        String,
        index=True
    )

    route_id = Column(
        String,
        index=True
    )


    direction = Column(String)

    timestamp = Column(
        String,
        index=True
    )


    # segment state
    segment_id = Column(
        String,
        index=True
    )

    segment_progress = Column(Float)


    # movement state
    speed = Column(Float)

    movement_state = Column(String)


    # route ordering
    stop_sequence = Column(
        Integer,
        nullable=True
    )


    # metadata
    confidence = Column(String)

    source = Column(String)

    simulation_flag = Column(Boolean)


    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )