"""Diagnostic script for self-loop segment analysis — read-only, no modifications."""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text
from database.connection import SessionLocal

db = SessionLocal()

# ---- 1. Self-loop counts ----
r = db.execute(text("""
    SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE from_stop_id = to_stop_id) as self_loops,
        COUNT(*) FILTER (WHERE from_stop_id != to_stop_id) as normal,
        COUNT(*) FILTER (WHERE from_stop_id IS NULL OR to_stop_id IS NULL) as null_stops
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND (metrics->>'travel_time') IS NOT NULL
""")).fetchone()
print("=" * 60)
print("SELF-LOOP ANALYSIS")
print("=" * 60)
print(f"Total segment_completed: {r[0]}")
print(f"Self-loops (from==to):   {r[1]} ({r[1]/r[0]*100:.2f}%)")
print(f"Normal (from!=to):       {r[2]} ({r[2]/r[0]*100:.2f}%)")
print(f"NULL stops:              {r[3]}")

# ---- 2. Top self-loop patterns ----
print()
print("TOP 15 SELF-LOOP segment_id PATTERNS:")
rows = db.execute(text("""
    SELECT segment_id, from_stop_id, to_stop_id, COUNT(*) as cnt
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND from_stop_id = to_stop_id
    AND (metrics->>'travel_time') IS NOT NULL
    GROUP BY segment_id, from_stop_id, to_stop_id
    ORDER BY cnt DESC
    LIMIT 15
""")).fetchall()
for row in rows:
    print(f"  seg={row[0]:20s}  from={row[1]:8s}  to={row[2]:8s}  count={row[3]}")

# ---- 3. Segment_id format analysis for self-loops ----
print()
print("SEGMENT_ID FORMAT ANALYSIS (self-loops):")
rows2 = db.execute(text("""
    SELECT segment_id, from_stop_id, to_stop_id,
           SPLIT_PART(segment_id, '_', 1) as seg_from,
           SPLIT_PART(segment_id, '_', 2) as seg_to
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND from_stop_id = to_stop_id
    AND (metrics->>'travel_time') IS NOT NULL
    LIMIT 10
""")).fetchall()
for row in rows2:
    sid_from = row[3]
    sid_to = row[4]
    match_type = "MISMATCH" if sid_from == sid_to else "from!=to_in_segid"
    print(f"  seg_id={row[0]:20s}  event_from={row[1]:8s}  event_to={row[2]:8s}  "
          f"seg_from={sid_from:8s}  seg_to={sid_to:8s}  [{match_type}]")

# ---- 4. Completion method breakdown ----
print()
print("COMPLETION METHOD BREAKDOWN:")
rows3 = db.execute(text("""
    SELECT
        metrics->>'completion_method' as method,
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE from_stop_id = to_stop_id) as self_loops
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND (metrics->>'travel_time') IS NOT NULL
    GROUP BY metrics->>'completion_method'
    ORDER BY total DESC
""")).fetchall()
for row in rows3:
    pct = row[2]/row[1]*100 if row[1] > 0 else 0
    print(f"  method={str(row[0]):25s}  total={row[1]:8d}  self_loops={row[2]:8d} ({pct:.1f}%)")

# ---- 5. Check: do self-loop events have valid travel_time? ----
print()
print("TRAVEL_TIME STATS FOR SELF-LOOPS vs NORMAL:")
rows4 = db.execute(text("""
    SELECT
        CASE WHEN from_stop_id = to_stop_id THEN 'self_loop' ELSE 'normal' END as category,
        COUNT(*) as cnt,
        AVG((metrics->>'travel_time')::float) as avg_tt,
        MIN((metrics->>'travel_time')::float) as min_tt,
        MAX((metrics->>'travel_time')::float) as max_tt
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND (metrics->>'travel_time') IS NOT NULL
    GROUP BY CASE WHEN from_stop_id = to_stop_id THEN 'self_loop' ELSE 'normal' END
""")).fetchall()
for row in rows4:
    print(f"  {row[0]:12s}  count={row[1]:8d}  avg_tt={row[2]:.1f}s  "
          f"min_tt={row[3]:.1f}s  max_tt={row[4]:.1f}s")

# ---- 6. Which source generates self-loops? (traversal vs dwell vs detector) ----
print()
print("SEGMENT_ID vs FROM_STOP analysis (self-loop rows):")
print("Does segment_id START with from_stop_id?")
rows5 = db.execute(text("""
    SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE segment_id LIKE from_stop_id || '_%') as seg_starts_with_from,
        COUNT(*) FILTER (WHERE segment_id LIKE '%_' || to_stop_id) as seg_ends_with_to,
        COUNT(*) FILTER (WHERE SPLIT_PART(segment_id,'_',1) = SPLIT_PART(segment_id,'_',2)) as seg_self_loop
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND from_stop_id = to_stop_id
    AND (metrics->>'travel_time') IS NOT NULL
""")).fetchone()
print(f"  Total self-loop events:         {rows5[0]}")
print(f"  segment_id STARTS with from:    {rows5[1]}")
print(f"  segment_id ENDS with to:        {rows5[2]}")
print(f"  segment_id itself is A_A form:  {rows5[3]}")

# ---- 7. Route distribution of self-loops ----
print()
print("SELF-LOOP BY ROUTE:")
rows6 = db.execute(text("""
    SELECT route_id,
           COUNT(*) as total_events,
           COUNT(*) FILTER (WHERE from_stop_id = to_stop_id) as self_loops,
           COUNT(*) FILTER (WHERE from_stop_id != to_stop_id) as normal
    FROM transit_events
    WHERE event_type = 'segment_completed'
    AND (metrics->>'travel_time') IS NOT NULL
    GROUP BY route_id
    ORDER BY self_loops DESC
""")).fetchall()
for row in rows6:
    pct = row[2]/row[1]*100 if row[1] > 0 else 0
    print(f"  route={row[0]:20s}  total={row[1]:7d}  self_loops={row[2]:7d} ({pct:.1f}%)  normal={row[3]:7d}")

db.close()
print()
print("ANALYSIS COMPLETE")
