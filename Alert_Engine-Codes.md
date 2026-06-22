alert_engine/rules.py:{
    from alert_engine.config import (
    ALERT_EXPIRY_DELAY,
    ALERT_EXPIRY_DWELL,
    DELAY_THRESHOLD_HIGH,
    DELAY_THRESHOLD_LOW,
    DELAY_THRESHOLD_MEDIUM,
    DWELL_THRESHOLD_HIGH,
    DWELL_THRESHOLD_MEDIUM,
)


def handle_segment_completed(event_row: dict, segment_stats_row: dict | None) -> dict | None:
    metrics = event_row.get("metrics") or {}
    travel_time = metrics.get("travel_time")
    if travel_time is None or segment_stats_row is None:
        return None

    avg_time = segment_stats_row.get("avg_travel_time")
    if avg_time is None or avg_time <= 0:
        return None

    ratio = float(travel_time) / float(avg_time)
    if ratio < DELAY_THRESHOLD_LOW:
        return None

    if ratio >= DELAY_THRESHOLD_HIGH:
        severity = "high"
    elif ratio >= DELAY_THRESHOLD_MEDIUM:
        severity = "medium"
    else:
        severity = "low"

    route_id = event_row.get("route_id") or "unknown"
    segment_id = event_row.get("segment_id") or "unknown"
    actual_min = round(float(travel_time) / 60, 1)
    expected_min = round(float(avg_time) / 60, 1)

    return {
        "type": "delay",
        "severity": severity,
        "message": (
            f"{route_id} vehicle delayed {actual_min} min on segment "
            f"{segment_id}. Expected {expected_min} min."
        ),
        "route_id": event_row.get("route_id"),
        "vehicle_id": event_row.get("vehicle_id"),
        "segment_id": event_row.get("segment_id"),
        "source_event_id": event_row.get("event_id"),
        "lat": event_row.get("lat"),
        "lon": event_row.get("lon"),
        "expires_minutes": ALERT_EXPIRY_DELAY,
    }


def handle_dwell_time(event_row: dict) -> dict | None:
    metrics = event_row.get("metrics") or {}
    dwell = metrics.get("dwell_time")
    if dwell is None or float(dwell) < DWELL_THRESHOLD_MEDIUM:
        return None

    severity = "high" if float(dwell) >= DWELL_THRESHOLD_HIGH else "medium"
    route_id = event_row.get("route_id") or "unknown"
    stop_id = event_row.get("stop_id") or "unknown"
    dwell_min = round(float(dwell) / 60, 1)

    return {
        "type": "dwell_issue",
        "severity": severity,
        "message": (
            f"{route_id} vehicle stationary at Stop {stop_id} for "
            f"{dwell_min} minutes. Possible breakdown."
        ),
        "route_id": event_row.get("route_id"),
        "vehicle_id": event_row.get("vehicle_id"),
        "segment_id": None,
        "source_event_id": event_row.get("event_id"),
        "lat": event_row.get("lat"),
        "lon": event_row.get("lon"),
        "expires_minutes": ALERT_EXPIRY_DWELL,
    }

}
alert_engine/engine.py:{
    import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from alert_engine.aggregator import check_route_disruptions
from alert_engine.deduplicator import should_create_alert
from alert_engine.models import Alert
from alert_engine.rules import handle_dwell_time, handle_segment_completed


logger = logging.getLogger(__name__)

DAY_TYPE_MAP = {
    "Monday": "weekday",
    "Tuesday": "weekday",
    "Wednesday": "weekday",
    "Thursday": "weekday",
    "Sunday": "weekday",
    "Friday": "friday",
    "Saturday": "saturday",
}


def _fetch_segment_stats(db: Session, event_row: dict) -> dict | None:
    day_type = DAY_TYPE_MAP.get(event_row.get("day_of_week"))
    if not day_type:
        return None

    row = db.execute(text("""
        SELECT avg_travel_time, std_travel_time, sample_count
        FROM segment_statistics
        WHERE segment_id = :segment_id
          AND route_id = :route_id
          AND direction = :direction
          AND day_type = :day_type
          AND time_period = :time_period
        LIMIT 1
    """), {
        "segment_id": event_row.get("segment_id"),
        "route_id": event_row.get("route_id"),
        "direction": event_row.get("direction"),
        "day_type": day_type,
        "time_period": event_row.get("time_period"),
    }).fetchone()

    return dict(row._mapping) if row else None


def _build_alert_orm(alert_dict: dict) -> Alert:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=alert_dict["expires_minutes"])

    return Alert(
        alert_id=uuid.uuid4(),
        type=alert_dict["type"],
        severity=alert_dict["severity"],
        message=alert_dict["message"],
        route_id=alert_dict.get("route_id"),
        vehicle_id=alert_dict.get("vehicle_id"),
        segment_id=alert_dict.get("segment_id"),
        source_event_id=alert_dict.get("source_event_id"),
        lat=alert_dict.get("lat"),
        lon=alert_dict.get("lon"),
        created_at=now,
        expires_at=expires_at,
        eta_based=False,
    )


def _fetch_segment_completed_events(db: Session):
    return db.execute(text("""
        SELECT event_id, event_type, vehicle_id, route_id,
               segment_id, direction, day_of_week, time_period,
               timestamp, metrics
        FROM transit_events
        WHERE event_type = 'segment_completed'
          AND (metrics->>'travel_time') IS NOT NULL
          AND (metrics->>'travel_time')::float > 30
    """)).fetchall()


def _fetch_dwell_events(db: Session):
    return db.execute(text("""
        SELECT event_id, event_type, vehicle_id, route_id,
               stop_id, timestamp, metrics
        FROM transit_events
        WHERE event_type = 'dwell_time'
    """)).fetchall()


def process_events_batch(db: Session) -> dict:
    logger.info("Alert Engine: starting batch processing")

    seg_events = _fetch_segment_completed_events(db)
    dwell_events = _fetch_dwell_events(db)

    delay_alerts_created = []
    alerts_to_insert = []
    created_count = 0
    skipped_dedup = 0

    for row in seg_events:
        event = dict(row._mapping)
        stats = _fetch_segment_stats(db, event)
        alert_dict = handle_segment_completed(event, stats)
        if alert_dict is None:
            continue

        if not should_create_alert(alert_dict.get("vehicle_id"), "delay", db):
            skipped_dedup += 1
            continue

        delay_alerts_created.append(alert_dict)
        alerts_to_insert.append(_build_alert_orm(alert_dict))
        created_count += 1

    for row in dwell_events:
        event = dict(row._mapping)
        alert_dict = handle_dwell_time(event)
        if alert_dict is None:
            continue

        if not should_create_alert(alert_dict.get("vehicle_id"), "dwell_issue", db):
            skipped_dedup += 1
            continue

        alerts_to_insert.append(_build_alert_orm(alert_dict))
        created_count += 1

    disruption_dicts = check_route_disruptions(delay_alerts_created)
    for alert_dict in disruption_dicts:
        if not should_create_alert(alert_dict.get("route_id"), "disruption", db):
            skipped_dedup += 1
            continue

        alerts_to_insert.append(_build_alert_orm(alert_dict))
        created_count += 1

    if alerts_to_insert:
        db.bulk_save_objects(alerts_to_insert)
        db.commit()
        logger.info("Alert Engine: inserted %s alerts", created_count)
    else:
        logger.info("Alert Engine: no new alerts generated")

    return {
        "alerts_created": created_count,
        "skipped_dedup": skipped_dedup,
        "delay_alerts": len(delay_alerts_created),
        "disruptions": len(disruption_dicts),
        "segment_events_checked": len(seg_events),
        "dwell_events_checked": len(dwell_events),
    }

}
alert_engine/aggregator.py:{
    from collections import defaultdict

from alert_engine.config import (
    ALERT_EXPIRY_DISRUPTION,
    DISRUPTION_THRESHOLD_HIGH,
    DISRUPTION_THRESHOLD_MEDIUM,
)


def check_route_disruptions(delay_alerts: list[dict]) -> list[dict]:
    route_vehicles = defaultdict(set)

    for alert in delay_alerts:
        if alert.get("severity") not in ("medium", "high"):
            continue

        route_id = alert.get("route_id")
        vehicle_id = alert.get("vehicle_id")
        if route_id and vehicle_id:
            route_vehicles[route_id].add(vehicle_id)

    disruption_alerts = []
    for route_id, vehicles in route_vehicles.items():
        count = len(vehicles)
        if count < DISRUPTION_THRESHOLD_MEDIUM:
            continue

        severity = "high" if count >= DISRUPTION_THRESHOLD_HIGH else "medium"
        disruption_alerts.append({
            "type": "disruption",
            "severity": severity,
            "message": (
                f"Service disruption on {route_id}. {count} vehicles "
                "experiencing severe delays."
            ),
            "route_id": route_id,
            "vehicle_id": None,
            "segment_id": None,
            "source_event_id": None,
            "lat": None,
            "lon": None,
            "expires_minutes": ALERT_EXPIRY_DISRUPTION,
        })

    return disruption_alerts

}
alert_engine/models.py:{
    import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from database.connection import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    message = Column(Text, nullable=False)
    route_id = Column(String(50), index=True)
    vehicle_id = Column(String(200), nullable=True)
    segment_id = Column(String(100), nullable=True)
    source_event_id = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    eta_based = Column(Boolean, default=False)

}