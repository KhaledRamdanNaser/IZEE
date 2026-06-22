(venv) PS C:\Users\mohamed\IZEE> git diff eta-engine-development -- event_engine
fatal: bad revision 'eta-engine-development'
(venv) PS C:\Users\mohamed\IZEE> git fetch origin
remote: Enumerating objects: 90, done.
remote: Counting objects: 100% (83/83), done.
remote: Compressing objects: 100% (28/28), done.
remote: Total 49 (delta 15), reused 47 (delta 13), pack-reused 0 (from 0)
Unpacking objects: 100% (49/49), 3.04 MiB | 1.08 MiB/s, done.
 * [new branch]      Khaled_TransitIngestion_Integration -> origin/Khaled_TransitIngestion_Integration
 * [new branch]      Transit_ingesion_integration -> origin/Transit_ingesion_integration
 * [new branch]      eta-engine-development -> origin/eta-engine-development
   2af77b4..1410399  transit-engine         -> origin/transit-engine
(venv) PS C:\Users\mohamed\IZEE> git branch -r
  origin/Claude_Bugs_Done_2
  origin/HEAD -> origin/main
  origin/Khaled_TransitIngestion_Integration
  origin/Transit_ingesion_integration
  origin/Vehicle-State-Refactored
  origin/claude_Checks_Done
  origin/eta-engine-development
  origin/integration-salah-youssof
  origin/main
  origin/salah-event-engine-29.4
  origin/salah-event-engine-final
  origin/segment_id-Bug-Fixed
  origin/transit-engine
(venv) PS C:\Users\mohamed\IZEE> git log --oneline --decorate --graph --all -30
* 9ad9b1b (origin/eta-engine-development) feat: Step 12A — compute current_delay offline
* 578b3b6 feat: segment_stats.py — full Option C viability via spatial aggregation
* 2442887 feat: ETA engine foundation — bulk replay pipeline, Option C schema, segment statistics
| * fa30290 (HEAD -> segment_id-Bug-Fixed, origin/segment_id-Bug-Fixed) fix: resolve segment_id bugs and add operational documentation reports
* 9ad9b1b (origin/eta-engine-development) feat: Step 12A — compute current_delay offline
* 578b3b6 feat: segment_stats.py — full Option C viability via spatial aggregation
* 2442887 feat: ETA engine foundation — bulk replay pipeline, Option C schema, segment statistics
| * fa30290 (HEAD -> segment_id-Bug-Fixed, origin/segment_id-Bug-Fixed) fix: resolve segment_id bugs and add operational documentation rep
orts
|/  
* 71703b3 (origin/Claude_Bugs_Done_2, Claude_Bugs_Done_2) fix: resolve bugs in vehicle routes and observation pipeline
* c59799f (origin/claude_Checks_Done, claude_Checks_Done)  claude_Checks_Dones
* 0f1f384 (origin/Vehicle-State-Refactored, Vehicle-State-Refactored) Full Pipeline till Event engine, Without Kalman filter
| * 1410399 (origin/transit-engine) Remove Python cache files
| * 2af77b4 Transit Engine implementation
| | * f0deb63 (origin/Khaled_TransitIngestion_Integration) Transit ingestion integration updates
| |/  
|/|   
* | 6ac5efa (origin/integration-salah-youssof, origin/Transit_ingesion_integration, integration-salah-youssof) Integration: Connected Transit Ingestion and Event Engine (cleaned cache)
* | df26a90 (origin/salah-event-engine-final, salah-event-engine-final, salah-event-engine-29.4) Update Event Engine: Finalized segment travel logic and CTA_M_112 test cases
* | 37b0454 (origin/salah-event-engine-29.4) WIP: Segment travel detection logic and travel time metrics:  modified:   api/routes/vehicle.
set mark: ...skipping...
* 9ad9b1b (origin/eta-engine-development) feat: Step 12A — compute current_delay offline
* 578b3b6 feat: segment_stats.py — full Option C viability via spatial aggregation
* 2442887 feat: ETA engine foundation — bulk replay pipeline, Option C schema, segment statistics
| * fa30290 (HEAD -> segment_id-Bug-Fixed, origin/segment_id-Bug-Fixed) fix: resolve segment_id bugs and add operational documentation reports
|/  
* 71703b3 (origin/Claude_Bugs_Done_2, Claude_Bugs_Done_2) fix: resolve bugs in vehicle routes and observation pipeline
* c59799f (origin/claude_Checks_Done, claude_Checks_Done)  claude_Checks_Dones
* 0f1f384 (origin/Vehicle-State-Refactored, Vehicle-State-Refactored) Full Pipeline till Event engine, Without Kalman filter
| * 1410399 (origin/transit-engine) Remove Python cache files
| * 2af77b4 Transit Engine implementation
| | * f0deb63 (origin/Khaled_TransitIngestion_Integration) Transit ingestion integration updates
| |/  
|/|   
* | 6ac5efa (origin/integration-salah-youssof, origin/Transit_ingesion_integration, integration-salah-youssof) Integration: Connected Transit Ingestion and Event Engine (cleaned cache)
* | df26a90 (origin/salah-event-engine-final, salah-event-engine-final, salah-event-engine-29.4) Update Event Engine: Finalized segment travel logic and CTA_M_112 test cases
* | 37b0454 (origin/salah-event-engine-29.4) WIP: Segment travel detection logic and travel time metrics:  modified:   api/routes/vehicle.
...skipping...
* 9ad9b1b (origin/eta-engine-development) feat: Step 12A — compute current_delay offline
* 578b3b6 feat: segment_stats.py — full Option C viability via spatial aggregation
* 2442887 feat: ETA engine foundation — bulk replay pipeline, Option C schema, segment statistics
| * fa30290 (HEAD -> segment_id-Bug-Fixed, origin/segment_id-Bug-Fixed) fix: resolve segment_id bugs and add operational documentation reports
|/  
* 71703b3 (origin/Claude_Bugs_Done_2, Claude_Bugs_Done_2) fix: resolve bugs in vehicle routes and observation pipeline
* c59799f (origin/claude_Checks_Done, claude_Checks_Done)  claude_Checks_Dones
* 0f1f384 (origin/Vehicle-State-Refactored, Vehicle-State-Refactored) Full Pipeline till Event engine, Without Kalman filter
| * 1410399 (origin/transit-engine) Remove Python cache files
| * 2af77b4 Transit Engine implementation
| | * f0deb63 (origin/Khaled_TransitIngestion_Integration) Transit ingestion integration updates
| |/  
|/|   
* | 6ac5efa (origin/integration-salah-youssof, origin/Transit_ingesion_integration, integration-salah-youssof) Integration: Connected Transit Ingestion and Event Engine (cleaned cache)
* | df26a90 (origin/salah-event-engine-final, salah-event-engine-final, salah-event-engine-29.4) Update Event Engine: Finalized segment travel logic and CTA_M_112 test cases
* | 37b0454 (origin/salah-event-engine-29.4) WIP: Segment travel detection logic and travel time metrics:  modified:   api/routes/vehicle.
py
* 578b3b6 feat: segment_stats.py — full Option C viability via spatial aggregation
* 2442887 feat: ETA engine foundation — bulk replay pipeline, Option C schema, segment statistics
| * fa30290 (HEAD -> segment_id-Bug-Fixed, origin/segment_id-Bug-Fixed) fix: resolve segment_id bugs and add operational documentation reports
|/  
* 71703b3 (origin/Claude_Bugs_Done_2, Claude_Bugs_Done_2) fix: resolve bugs in vehicle routes and observation pipeline
* c59799f (origin/claude_Checks_Done, claude_Checks_Done)  claude_Checks_Dones
* 0f1f384 (origin/Vehicle-State-Refactored, Vehicle-State-Refactored) Full Pipeline till Event engine, Without Kalman filter
| * 1410399 (origin/transit-engine) Remove Python cache files
| * 2af77b4 Transit Engine implementation
| | * f0deb63 (origin/Khaled_TransitIngestion_Integration) Transit ingestion integration updates
| |/  
|/|   
* | 6ac5efa (origin/integration-salah-youssof, origin/Transit_ingesion_integration, integration-salah-youssof) Integration: Connected Transit Ingestion and Event Engine (cleaned cache)
* | df26a90 (origin/salah-event-engine-final, salah-event-engine-final, salah-event-engine-29.4) Update Event Engine: Finalized segment travel logic and CTA_M_112 test cases
* | 37b0454 (origin/salah-event-engine-29.4) WIP: Segment travel detection logic and travel time metrics:  modified:   api/routes/vehicle.py
* | 81f704d WIP: Event Engine Phase 1 and 2 complete, integrated with vehicle location endpoint
|/  
* 8775623 (origin/main, origin/HEAD, main, Salah-vehicle-live-endpoint) Removed venv and cache files
* e58b941 Initial commit - Vehicle State Engine + API + DB integration
(END)
new terminal:PS C:\Users\mohamed\IZEE> (Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& c:\Users\mohamed\IZEE\venv\Scripts\Activate.ps1)
(venv) PS C:\Users\mohamed\IZEE> git merge-base segment_id-Bug-Fixed origin/eta-engine-development
71703b312010bc91ed935174a9f5b3db7927df7d
(venv) PS C:\Users\mohamed\IZEE> 
(venv) PS C:\Users\mohamed\IZEE> git show <hash> --oneline
At line:1 char:10
+ git show <hash> --oneline
+          ~
The '<' operator is reserved for future use.
    + CategoryInfo          : ParserError: (:) [], ParentContainsErrorRecordException
    + FullyQualifiedErrorId : RedirectionNotSupported
 
(venv) PS C:\Users\mohamed\IZEE> git diff origin/eta-engine-development -- event_engine
diff --git a/event_engine/dwell_lifecycle.py b/event_engine/dwell_lifecycle.py
index d14d9c7..77e3638 100644
--- a/event_engine/dwell_lifecycle.py
+++ b/event_engine/dwell_lifecycle.py
@@ -52,8 +52,9 @@ def process_dwell_lifecycle(
             )
 
             # check traversal completion
-            stored = get_active_traversal(vehicle_id)
+           # stored = get_active_traversal(vehicle_id)
 
+            """"
             if stored:
 
                 try:
@@ -97,19 +98,21 @@ def process_dwell_lifecycle(
 
                 # cleanup traversal lifecycle
                 clear_traversal(vehicle_id)
-
+            """  
         # -----------------------------------
         # DEPARTURE
         # -----------------------------------
 
         elif event_type == "stop_departure":
 
+            """
             start_traversal(
                 vehicle_id,
                 stop_id,
                 timestamp,
                 current_state.get("segment_id")
             )
+            """
 
             stored_dwell = get_active_dwell(
                 vehicle_id
diff --git a/event_engine/traversal_lifecycle.py b/event_engine/traversal_lifecycle.py
index 4f5b651..6802c75 100644
--- a/event_engine/traversal_lifecycle.py
+++ b/event_engine/traversal_lifecycle.py
@@ -76,7 +76,7 @@ def process_traversal_lifecycle(
                     )
 
                     return generated_events
-
+                                
 
 
                 raw_segment_completed = {
@@ -266,15 +266,20 @@ def process_traversal_lifecycle(
                     []
                 )
 
-                # --- KHALED EDIT START ---
                 for segment in segments:
 
-                    if segment["start"]["stop_id"] == stop_id:
+                    from_stop_id = (
+                        segment.get("from_stop_id")
+                        or segment.get("start", {}).get("stop_id")
+                    )
 
-                        departure_segment = segment["segment_id"]
-                        break
-                # --- KHALED EDIT END ---
+                    if from_stop_id == stop_id:
 
+                        departure_segment = segment.get(
+                            "segment_id"
+                        )
+
+                        break
 
             if departure_segment:
 
@@ -353,4 +358,4 @@ def process_traversal_lifecycle(
             clear_traversal(vehicle_id)
 
 
-    return generated_events
+    return generated_events
\ No newline at end of file