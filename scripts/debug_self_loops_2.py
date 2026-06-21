"""Diagnostic Part 2: Deep trace of HOW from_stop_id gets set to to_stop_id."""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from database.connection import SessionLocal

db = SessionLocal()

# ---- KEY QUESTION: segment_id = "A_B" but from_stop_id = B and to_stop_id = B ----
# The segment_id is constructed as "{from_stop}_{to_stop}" in reference/loader.py
# But the event's from_stop_id == to_stop_id == B (the END of the segment)
# This means from_stop_id is being set to the TO stop, not the FROM stop.

# Check: for self-loop events, does from_stop_id always == segment_id's SECOND part?
print("=" * 70)
print("DEEP TRACE: from_stop_id vs segment_id components")
print("=" * 70)

r = db.execute(text("""
    SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE from_stop_id = SPLIT_PART(segment_id, '_', 2)) as from_equals_seg_to,
        COUNT(*) FILTER (WHERE from_stop_id = SPLIT_PART(segment_id, '_', 1)) as from_equals_seg_from,
        COUNT(*) FILTER (WHERE to_stop_id   = SPLIT_PART(segment_id, '_', 2)) as to_equals_seg_to
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND from_stop_id = to_stop_id
    AND (metrics->>'travel_time') IS NOT NULL
""")).fetchone()
print(f"Total self-loops: {r[0]}")
print(f"  from_stop_id == seg_part2 (to):   {r[1]} ({r[1]/r[0]*100:.1f}%)")
print(f"  from_stop_id == seg_part1 (from):  {r[2]} ({r[2]/r[0]*100:.1f}%)")
print(f"  to_stop_id   == seg_part2 (to):    {r[3]} ({r[3]/r[0]*100:.1f}%)")

# ---- Check completion_method for the two sources ----
print()
print("=" * 70)
print("SELF-LOOP: segment_transition source trace")
print("=" * 70)
# In traversal_lifecycle.py line 89:
#   "to_stop_id": stored_segment.split("_")[1]
# This uses the SECOND part of segment_id.
# But from_stop_id comes from active_traversal["from_stop_id"]
# which is set by start_traversal(vehicle_id, from_stop_id=..., ...)

# In segment_transition completion (traversal_lifecycle line 82-99):
#   from_stop_id = active_traversal["from_stop_id"]
#   to_stop_id   = stored_segment.split("_")[1]
# If from_stop_id was the END stop of the previous segment, that's the bug.

# In stop_arrival completion (traversal_lifecycle line 324-336):
#   from_stop_id = stored["from_stop_id"]
#   to_stop_id   = stop_id (the arrival stop)
# If stored["from_stop_id"] == stop_id, self-loop happens.

# Let's check: for dwell_lifecycle (line 73-84):
#   from_stop_id = stored["from_stop_id"]
#   to_stop_id   = stop_id (arrival stop)
# Same pattern.

# Now trace WHERE from_stop_id gets set in start_traversal:
# traversal_lifecycle.py line 122-127 (after segment_transition):
#   start_traversal(vehicle_id, current_segment.split("_")[0], ...)
#   -> from_stop_id = FIRST part of new segment_id
# This is correct for the NEXT traversal.

# But line 218-219 (bootstrap fallback):
#   origin_stop_id = segment_id.split("_")[0]
# This is also correct.

# Line 281-286 (stop_departure):
#   start_traversal(vehicle_id, stop_id, timestamp, departure_segment)
#   -> from_stop_id = stop_id (the departure stop)

# WAIT: Line 244-246 (stop_departure in traversal_lifecycle):
#   departure_segment = current_state.get("segment_id")
# But this is the CURRENT matched segment. After a stop_departure,
# the vehicle is NOW moving away from the stop. The segment_id in
# current_state is the segment the vehicle is CURRENTLY on.

# KEY INSIGHT: In vehicle_state/engine.py line 89:
#   "stop_sequence": end["sequence"]
# And line 43:
#   next_stop_id = end["stop_id"]
# And line 91:
#   "segment_id": segment["segment_id"]

# So for segment "A_B":
#   next_stop_id = B (end of segment)
#   stop_sequence = B's sequence
#   segment_id = "A_B"

# When vehicle arrives at stop B:
#   movement_state = "at_stop"
#   current_stop_id = next_stop_id = B

# stop_arrival event: stop_id = next_stop_id = B
# In traversal lifecycle, on stop_arrival:
#   stored["from_stop_id"] might be B if the previous start_traversal was
#   called with the WRONG from_stop_id.

# Let's check: what's the from_stop_id pattern for normal events?
print()
print("FOR NORMAL EVENTS (from!=to):")
r2 = db.execute(text("""
    SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE from_stop_id = SPLIT_PART(segment_id, '_', 1)) as from_matches_seg_from,
        COUNT(*) FILTER (WHERE to_stop_id = SPLIT_PART(segment_id, '_', 2)) as to_matches_seg_to,
        COUNT(*) FILTER (WHERE from_stop_id = SPLIT_PART(segment_id, '_', 2)) as from_matches_seg_to
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND from_stop_id != to_stop_id
    AND (metrics->>'travel_time') IS NOT NULL
""")).fetchone()
print(f"Total normal events: {r2[0]}")
print(f"  from_stop_id == seg_part1 (correct): {r2[1]} ({r2[1]/r2[0]*100:.1f}%)")
print(f"  to_stop_id   == seg_part2 (correct): {r2[2]} ({r2[2]/r2[0]*100:.1f}%)")
print(f"  from_stop_id == seg_part2 (wrong):   {r2[3]} ({r2[3]/r2[0]*100:.1f}%)")

# ---- Check: how traversal is started BEFORE self-loop events ----
# The critical question: is from_stop_id being set to the destination stop
# of the PREVIOUS segment instead of the origin stop of the CURRENT segment?
print()
print("=" * 70)
print("DWELL vs TRAVERSAL self-loop contribution")
print("=" * 70)
# Note: dwell_lifecycle also generates segment_completed but WITHOUT
# completion_method in metrics. Let's check for NULL method.
r3 = db.execute(text("""
    SELECT
        metrics->>'completion_method' as method,
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE from_stop_id = to_stop_id) as self_loops,
        COUNT(*) FILTER (WHERE from_stop_id = SPLIT_PART(segment_id, '_', 2)) as from_is_seg_end,
        COUNT(*) FILTER (WHERE from_stop_id = SPLIT_PART(segment_id, '_', 1)) as from_is_seg_start
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND (metrics->>'travel_time') IS NOT NULL
    GROUP BY metrics->>'completion_method'
""")).fetchall()
for row in r3:
    print(f"  method={str(row[0]):25s} total={row[1]:8d} self_loops={row[2]:8d} "
          f"from=seg_end={row[3]:8d} from=seg_start={row[4]:8d}")

db.close()
print()
print("ANALYSIS PART 2 COMPLETE")
