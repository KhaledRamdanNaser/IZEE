
# 🧠 IZEE PIPELINE FIX TASK (FOR VEHICLE STATE + EVENT ENGINE)

## 🎯 GOAL (VERY IMPORTANT)

Make sure:

> ❗ Event data is consistent, unique, and identical across all pipeline layers
> so Alert Engine and SegmentStats can trust it.

---

# 🚨 CURRENT PROBLEM (SIMPLE EXPLANATION)

Right now the system has 3 issues:

---

## ❌ 1. TWO DIFFERENT WAYS TO END A SEGMENT

We currently have:

### A. stop_arrival → segment_completed

### B. segment_transition → segment_completed

👉 Problem:
Same segment can be completed in 2 different ways.

### 💥 Effect:

* duplicate or inconsistent travel_time
* wrong statistics
* Alert Engine becomes unstable

---

## ❌ 2. SEGMENT ID IS NOT 100% CONSISTENT

* Vehicle State uses GPS-based segment_id
* SegmentStats uses merged/normalized segment_id
* Event Engine uses raw segment_id

👉 Problem:
Same real-world segment = different IDs in different layers

### 💥 Effect:

* missing stats (NULL lookups)
* alerts skipped
* inconsistent matching

---

## ❌ 3. EVENT STREAM IS NOT CLEAN

We currently generate extra or noisy events:

* segment_travel (should NOT be used in analytics)
* overlapping segment_completed events
* bootstrap-generated edge cases

### 💥 Effect:

* noisy data in SegmentStats
* wrong alert thresholds
* false/missing alerts

---

# 🧩 WHAT YOU NEED TO FIX (VERY CLEAR TASKS)

---

# 🔴 TASK 1 — MAKE SINGLE SOURCE OF TRUTH FOR SEGMENT COMPLETION

## RULE:

> Only ONE method is allowed to create `segment_completed`

### Choose ONE:

✔ Preferred: `segment_transition` (GPS-based)
OR
✔ fallback: `stop_arrival`

---

## MUST DO:

* remove dual completion logic
* enforce single path
* ensure no duplicate segment_completed for same segment

---

# 🔴 TASK 2 — FIX SEGMENT ID CONSISTENCY

## RULE:

> All layers must use the SAME segment_id definition

### REQUIRED:

* Vehicle State
* Event Engine
* SegmentStats

ALL MUST USE:

> same canonical segment_id format

---

## MUST DO:

* stop using raw + derived mixed IDs
* ensure segment_id is stable after assignment
* no silent remapping differences

---

# 🔴 TASK 3 — CLEAN EVENT STREAM

## MUST REMOVE or ISOLATE:

* segment_travel from analytics path
* duplicate segment_completed events
* invalid bootstrap completions

---

## RULE:

> Only CLEAN segment_completed should enter SegmentStats + Alert Engine

---

# 🟠 TASK 4 — FIX STOP DEPARTURE CONSISTENCY

## RULE:

stop_departure must always mean:

> vehicle is leaving CURRENT stop (not next stop)

---

## MUST ENSURE:

* NO fallback using next_stop_id
* stop_id must always be correct physical stop

---

# 🟠 TASK 5 — ADD EVENT VALIDATION LAYER (IMPORTANT)

Before writing to DB:

Validate:

* travel_time > 0
* no duplicate segment_completed for same vehicle + segment
* segment_id is valid
* no conflicting completion methods

---

# 🧠 WHY THIS IS IMPORTANT 

If these are NOT fixed:

👉 Alert Engine will:

* miss real delays
* create inconsistent alerts
* fail to match SegmentStats
* behave differently on replay vs real-time

---

# 🔥 SIMPLE SUMMARY 

> “We are not changing Alert Engine. We are fixing the event truth layer so Alert Engine can trust the data.”

---

# 🚀 PRIORITY ORDER

do in this order:

### 1️⃣ Fix single segment completion rule (MOST IMPORTANT)

### 2️⃣ Unify segment_id definition across system

### 3️⃣ Remove segment_travel from analytics

### 4️⃣ Fix stop_departure correctness

### 5️⃣ Add validation layer

---

# 🧠 ONE-LINE FINAL MESSAGE 
> “Fix event truth consistency first (single segment_completed source + unified segment_id). Alert Engine issues are mostly caused by inconsistent event definitions, not the alert logic itself.”

