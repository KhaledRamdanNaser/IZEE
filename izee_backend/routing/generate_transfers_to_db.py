from routing.gtfs_loader import load_multiple_gtfs
from routing.transfer_builder import build_metro_access_transfers, build_walking_transfers
from database.connection import SessionLocal, Base, engine
from models.walking_transfer import WalkingTransfer

GTFS_PATHS = [
    "C:\\Users\\omaro\\Desktop\\semeser 8\\link (7)",
    "C:\\Users\\omaro\\Desktop\\semeser 8\\Metro-GTFS-master\\Metro-GTFS-master",
]

Base.metadata.create_all(bind=engine)

stops, stop_times, trips, routes, calendar, frequencies, shapes = load_multiple_gtfs(GTFS_PATHS)

normal_transfers = build_walking_transfers(
    stops,
    max_walk_meters=1500,
    walking_speed_mps=1.3
)

metro_access_transfers = build_metro_access_transfers(
    stops,
    min_walk_meters=500,
    max_walk_meters=800,
    walking_speed_mps=1.3
)

emergency_transfers = build_walking_transfers(
    stops,
    max_walk_meters=3000,
    walking_speed_mps=1.3
)

db = SessionLocal()

try:
    # remove old transfers before regenerating
    db.query(WalkingTransfer).delete()

    count = 0
    seen_normal_pairs = set()

    # Save normal stop-to-stop transfers used during normal routing.
    for from_stop_id, edges in normal_transfers.items():
        for edge in edges:
            key = (str(from_stop_id), str(edge["to"]), "normal_transfer")
            seen_normal_pairs.add(key)

            transfer = WalkingTransfer(
                from_stop_id=key[0],
                to_stop_id=key[1],
                walk_type=key[2],
                distance_meters=float(edge["distance_meters"]),
                walking_time=int(edge["walking_time"])
            )

            db.add(transfer)
            count += 1

            if count % 1000 == 0:
                db.commit()
                print(f"Saved {count} transfers...")

    # This is now mostly covered by the 1500m normal walking radius, but keep it
    # harmless in case the metro-specific logic changes later.
    for from_stop_id, edges in metro_access_transfers.items():
        for edge in edges:
            key = (str(from_stop_id), str(edge["to"]), "normal_transfer")

            if key in seen_normal_pairs:
                continue

            seen_normal_pairs.add(key)

            transfer = WalkingTransfer(
                from_stop_id=key[0],
                to_stop_id=key[1],
                walk_type=key[2],
                distance_meters=float(edge["distance_meters"]),
                walking_time=int(edge["walking_time"])
            )

            db.add(transfer)
            count += 1

            if count % 1000 == 0:
                db.commit()
                print(f"Saved {count} transfers...")

    # Save longer fallback access transfers separately from normal routing.
    for from_stop_id, edges in emergency_transfers.items():
        for edge in edges:
            if float(edge["distance_meters"]) <= 1500:
                continue

            transfer = WalkingTransfer(
                from_stop_id=str(from_stop_id),
                to_stop_id=str(edge["to"]),
                walk_type="emergency_access",
                distance_meters=float(edge["distance_meters"]),
                walking_time=int(edge["walking_time"])
            )

            db.add(transfer)
            count += 1

            if count % 1000 == 0:
                db.commit()
                print(f"Saved {count} transfers...")

    db.commit()
    print(f"Done. Saved {count} walking transfers.")

except Exception as e:
    db.rollback()
    print("Error:", e)

finally:
    db.close()
