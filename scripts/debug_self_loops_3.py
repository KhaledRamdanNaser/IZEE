"""Diagnostic Part 3: Check for duplicate segment_completed events from dual generation paths."""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from database.connection import SessionLocal

db = SessionLocal()

# ---- Check: same vehicle, same segment_id, same timestamp, different completion_method ----
print("=" * 70)
print("DUPLICATE DETECTION: same (vehicle, segment, ~timestamp) different method")
print("=" * 70)

# Check if we have segment_completed pairs within 1 second of each other
# for the same vehicle and segment
r = db.execute(text("""
    WITH events AS (
        SELECT
            event_id,
            vehicle_id,
            segment_id,
            timestamp,
            from_stop_id,
            to_stop_id,
            metrics->>'completion_method' as method,
            (metrics->>'travel_time')::float as travel_time
        FROM transit_events
        WHERE event_type = 'segment_completed'
        AND (metrics->>'travel_time') IS NOT NULL
    )
    SELECT
        a.vehicle_id,
        a.segment_id,
        a.timestamp as ts_a,
        b.timestamp as ts_b,
        a.method as method_a,
        b.method as method_b,
        a.from_stop_id as from_a,
        a.to_stop_id as to_a,
        b.from_stop_id as from_b,
        b.to_stop_id as to_b,
        a.travel_time as tt_a,
        b.travel_time as tt_b
    FROM events a
    JOIN events b
        ON a.vehicle_id = b.vehicle_id
        AND a.segment_id = b.segment_id
        AND a.event_id != b.event_id
        AND a.timestamp = b.timestamp
        AND a.method != b.method
    LIMIT 20
""")).fetchall()

print(f"Duplicate pairs found (same vehicle+segment+timestamp, different method): {len(r)}")
for row in r:
    print(f"  veh={row[0][:40]}  seg={row[1]:15s}  "
          f"method_a={row[4]:20s} method_b={row[5]:20s}  "
          f"from_a={row[6]:6s} to_a={row[7]:6s}  "
          f"from_b={row[8]:6s} to_b={row[9]:6s}  "
          f"tt_a={row[10]:.0f}s  tt_b={row[11]:.0f}s")

# ---- How many total duplicates by expanding window? ----
print()
print("DUPLICATE COUNT (exact timestamp match, same vehicle+segment, different method):")
r2 = db.execute(text("""
    WITH events AS (
        SELECT event_id, vehicle_id, segment_id, timestamp,
               metrics->>'completion_method' as method
        FROM transit_events
        WHERE event_type = 'segment_completed'
        AND (metrics->>'travel_time') IS NOT NULL
    )
    SELECT COUNT(*) / 2 as duplicate_pairs
    FROM events a
    JOIN events b
        ON a.vehicle_id = b.vehicle_id
        AND a.segment_id = b.segment_id
        AND a.event_id < b.event_id
        AND a.timestamp = b.timestamp
        AND a.method != b.method
""")).fetchone()
print(f"  Total duplicate pairs: {r2[0]}")

# ---- Self-loop: is the from_stop_id always the NEXT_STOP_ID (end of segment)? ----
print()
print("=" * 70)
print("VEHICLE STATE: next_stop_id analysis")
print("=" * 70)
# In vehicle_state/engine.py, next_stop_id = end["stop_id"] = segment's END stop
# In detectors.py, stop_arrival: stop_id = current_state["next_stop_id"] = END stop
# In detectors.py, stop_departure: stop_id = previous_state["next_stop_id"] = END stop
# 
# In traversal_lifecycle.py, on stop_departure event:
#   start_traversal(vehicle_id, stop_id, ..., departure_segment)
#   BUT stop_id here = previous_state["next_stop_id"] = END stop of previous segment
#   
# So if vehicle was on segment "A_B" and arrives at B, then departs:
#   stop_departure: stop_id = B (because next_stop_id was B while at that stop)
#   start_traversal(vehicle_id, from_stop_id=B, ..., segment="B_C")
#   Now when it completes segment "B_C":
#     from_stop_id = B (correct!)
#   
# But what about segment_transition completion?
#   stored_segment changes: "A_B" -> "B_C"
#   In traversal line 85-89:
#     from_stop_id = active_traversal["from_stop_id"]
#     to_stop_id = stored_segment.split("_")[1] = B
#   
#   If from_stop_id was set to B at start (which happens when departure_segment
#   didn't match stop_id), then from_stop_id=B, to_stop_id=B -> SELF LOOP!

# Let's verify: when does departure_segment NOT start with stop_id?
# traversal_lifecycle line 248-255:
#   departure_segment = current_state.get("segment_id")
#   if departure_segment and not departure_segment.startswith(f"{stop_id}_"):
#       departure_segment = None
# Then it falls through to the GTFS lookup.
# 
# But if GTFS lookup fails or finds wrong segment, start_traversal
# might get called with stop_id as from_stop_id BUT a segment_id
# that starts with a DIFFERENT stop.
# That's one path.
#
# But the MAIN path is the bootstrap at line 170-228.
# Bootstrap: from_stop_id = origin_stop_id
#   If origin_stop = stops_map.get(current_sequence - 1)
#   = the PREVIOUS stop in sequence
#   But wait: stop_sequence in vehicle_state = end["sequence"]
#   So current_sequence = end_stop_sequence
#   origin_sequence = end_stop_sequence - 1
#   That would be the START of the current segment (correct!)
#   Unless stop_sequence numbering doesn't start at 1 or has gaps.

# Let's check stop_sequence gaps:
print()
print("STOP SEQUENCE GAP CHECK (are there gaps in sequences?):")
r3 = db.execute(text("""
    SELECT t.route_id, t.direction_id, st.stop_sequence
    FROM stop_time st
    JOIN trip t ON st.trip_id = t.trip_id
    WHERE t.route_id IN ('CTA_80', 'CTA_975', 'P_O_14_IG066', 'CTA_914', 'CTA_1073')
    ORDER BY t.route_id, t.direction_id, st.stop_sequence
""")).fetchall()

from collections import defaultdict
route_seqs = defaultdict(list)
for row in r3:
    key = (row[0], row[1])
    route_seqs[key].append(row[2])

for key, seqs in sorted(route_seqs.items()):
    unique = sorted(set(seqs))
    expected = list(range(min(unique), max(unique) + 1))
    gaps = set(expected) - set(unique)
    print(f"  route={key[0]:20s} dir={key[1]}  seqs={min(unique)}-{max(unique)}  "
          f"count={len(unique)}  gaps={len(gaps)} {'[HAS GAPS]' if gaps else '[OK]'}")
    if gaps:
        print(f"    Missing: {sorted(gaps)[:10]}...")

db.close()
print()
print("ANALYSIS PART 3 COMPLETE")
