from datetime import datetime, timedelta
from fastapi import HTTPException
import pytz

# Validate Egyptian Timestamp
def normalize_timestamp(ts: datetime):
    # Normalize 2l timestamp
    cairo_tz = pytz.timezone("Africa/Cairo")

    if ts.tzinfo is None:
        ts = cairo_tz.localize(ts)

    ts = ts.astimezone(pytz.UTC)

    # Get time bta3 dlw2ty in UTC
    now = datetime.now(pytz.UTC)

    if ts > now + timedelta(minutes=5):
        raise HTTPException(400, "future timestamp")

    if ts < now - timedelta(hours=2):
        raise HTTPException(400, "stale timestamp")

    # 2bl 2lsave fel database convert l naive UTC
    return ts.replace(tzinfo=None)

# Validate Location
def validate_location(lat: float, lon: float):
    if not (-90 <= lat <= 90):
        raise HTTPException(400, "invalid latitude")

    if not (-180 <= lon <= 180):
        raise HTTPException(400, "invalid longitude")

# Validate speed lw feh
def validate_speed(speed: float | None):
    if speed is not None:
        if speed < 0:
            raise HTTPException(400, "negative speed")
        if speed >= 130:
            raise HTTPException(400, "unrealistic speed")

# Validate bearing lw feh
def validate_bearing(bearing: float | None):
    if bearing is not None:
        if not (0 <= bearing <= 360):
            raise HTTPException(400, "invalid bearing")
        

"""from datetime import datetime, timedelta
from fastapi import HTTPException
import pytz


def validate_all(data):
    # --- LOCATION ---
    if not (-90 <= data.lat <= 90):
        raise HTTPException(400, "invalid latitude")

    if not (-180 <= data.lon <= 180):
        raise HTTPException(400, "invalid longitude")

    # --- TIMESTAMP ---
    cairo_tz = pytz.timezone("Africa/Cairo")

    ts = data.timestamp

    if ts.tzinfo is None:
        ts = cairo_tz.localize(ts)

    ts = ts.astimezone(pytz.UTC)

    now = datetime.now(pytz.UTC)

    if ts > now + timedelta(minutes=5):
        raise HTTPException(400, "future timestamp")

    if ts < now - timedelta(hours=2):
        raise HTTPException(400, "stale timestamp")

    # --- SPEED ---
    if data.speed is not None:
        if data.speed < 0:
            raise HTTPException(400, "negative speed")
        if data.speed >= 130:
            raise HTTPException(400, "unrealistic speed")

    # --- BEARING ---
    if data.bearing is not None:
        if not (0 <= data.bearing <= 360):
            raise HTTPException(400, "invalid bearing")

    # return normalized timestamp
    return ts.replace(tzinfo=None)"""