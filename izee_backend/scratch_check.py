from database.connection import SessionLocal
from models.shape import Shape
from models.trip import Trip

db = SessionLocal()
try:
    shape_count = db.query(Shape).count()
    trip_count = db.query(Trip).count()
    trips_with_shape = db.query(Trip).filter(Trip.shape_id != None).count()
    print("--- Database Check ---")
    print(f"Total shapes in DB: {shape_count}")
    print(f"Total trips in DB: {trip_count}")
    print(f"Trips with shape_id in DB: {trips_with_shape}")
    
    if shape_count > 0:
        sample_shapes = db.query(Shape).limit(5).all()
        print("Sample shapes:")
        for s in sample_shapes:
            print(f"  shape_id: {s.shape_id}, lat: {s.lat}, lon: {s.lon}, seq: {s.sequence}")
            
    if trips_with_shape > 0:
        sample_trips = db.query(Trip).filter(Trip.shape_id != None).limit(5).all()
        print("Sample trips with shapes:")
        for t in sample_trips:
            print(f"  trip_id: {t.trip_id}, route_id: {t.route_id}, shape_id: {t.shape_id}")
finally:
    db.close()
