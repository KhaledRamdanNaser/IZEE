from database.connection import SessionLocal
from models.trip import Trip
from models.stop_time import StopTime
from models.stop import Stop


def load_route_reference(route_id: str):
    db = SessionLocal()

    # 1️⃣ Get one trip for this route
    trip = db.query(Trip).filter(Trip.route_id == route_id).first()

    if not trip:
        raise Exception(f"No trip found for route {route_id}")

    # 2️⃣ Get ordered stop_times
    stop_times = (
        db.query(StopTime)
        .filter(StopTime.trip_id == trip.trip_id)
        .order_by(StopTime.stop_sequence)
        .all()
    )

    # 3️⃣ Join with stops
    stops = []
    for st in stop_times:
        stop = db.query(Stop).filter(Stop.stop_id == st.stop_id).first()

        stops.append({
            "stop_id": stop.stop_id,
            "lat": stop.lat,
            "lon": stop.lon,
            "sequence": st.stop_sequence
        })

    db.close()
    


    stops_by_sequence = {}

    for stop in stops:
        seq = stop["sequence"]
        stops_by_sequence[seq] = {
            "stop_id": stop["stop_id"],
            "lat": stop["lat"],
            "lon": stop["lon"]
    }





    # 4️⃣ Build segments
    segments = []
    for i in range(len(stops) - 1):
        segments.append({
            "segment_id": f"{stops[i]['stop_id']}_{stops[i+1]['stop_id']}",
            "start": stops[i],
            "end": stops[i + 1]
        })

    return {
        "route_id": route_id,
        "stops": stops,
        "segments": segments,
        "stops_by_sequence": stops_by_sequence   # 🔥 ADD THIS
    }