from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from alert_engine.config import DEDUP_WINDOW_MINUTES


_active_alerts_cache = {}


def should_create_alert(entity_id: str | None, alert_type: str, db: Session) -> bool:
    """
    Return False when the same entity already has this alert type inside
    the deduplication window. entity_id is vehicle_id for vehicle alerts
    and route_id for route-level disruption alerts.
    """
    if not entity_id:
        return True

    key = (entity_id, alert_type)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)

    cached_at = _active_alerts_cache.get(key)
    if cached_at and cached_at >= window_start:
        return False
    if cached_at:
        del _active_alerts_cache[key]

    result = db.execute(text("""
        SELECT created_at
        FROM alerts
        WHERE type = :alert_type
          AND created_at >= :window_start
          AND (
              vehicle_id = :entity_id
              OR route_id = :entity_id
          )
        LIMIT 1
    """), {
        "alert_type": alert_type,
        "window_start": window_start,
        "entity_id": entity_id,
    }).fetchone()

    if result:
        return False

    _active_alerts_cache[key] = now
    return True


def clear_cache() -> None:
    _active_alerts_cache.clear()
