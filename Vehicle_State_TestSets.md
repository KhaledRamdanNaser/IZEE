Test Case 1 — Between Stops Movement Processing

Purpose



Verify that a normal moving vehicle is correctly matched to the route and converted into a live operational state.



This validates:



map matching

segment identification

progress calculation

next stop detection

movement classification 

test set :{{

"scenario_name": "BetweenStopsMovementProcessing",

"vehicle_id": "V_Engine_Between_99",

"expected_behavior": [

"between_stops",

"segment_progress_calculated",

"next_stop_identified"

],

"observations": [

{

"vehicle_id": "V_Engine_Between_99",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T12:00:00",

"lat": 30.0301356,

"lon": 31.2402126,

"speed": 35.5,

"bearing": 56

}

]

}}, output :RUNNING: BetweenStopsMovementProcessing [1/1] ========== VEHICLE STATE RESULT ========== Vehicle: V_Engine_Between_99 Movement State: between_stops Matched Segment: 162_679 Segment Progress: 0.4999992565509095 Route Progress: 0.009433948236809613 Current Stop: None Next Stop: 679 Distance To Next Stop: 342.6682364836757 Events: None

, Test Case 2 — Approaching Stop Detection



Very important because your code has convergence logic.



Your code does NOT simply say:



distance < 150 → approaching



It requires:



distance decreasing compared to previous observation



So this needs two requests.

Expected sequence:



Observation 1:



between_stops



Observation 2:



approaching_stop



Expected:



Check	Result

Previous distance stored	PASS

Distance decreases	PASS

Approach detected	PASS

movement_state = approaching_stop	PASS



Evidence:



Logs:



DISTANCE TO NEXT STOP:

previous distance > current distance

STATE: approaching_stop



DB:



movement_state = approaching_stop

distance_to_next_stop < previous

test set :{{

"scenario_name": "ApproachingStopDetection",

"vehicle_id": "V_Engine_Approach_88",

"expected_behavior": [

"between_stops",

"approaching_stop"

],

"observations": [

{

"vehicle_id": "V_Engine_Approach_88",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T12:10:00",

"lat": 30.0311221,

"lon": 31.2415512,

"speed": 32.0,

"bearing": 56

},

{

"vehicle_id": "V_Engine_Approach_88",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T12:10:20",

"lat": 30.0317500,

"lon": 31.2425500,

"speed": 20.0,

"bearing": 57

}

]

}}, output :{RUNNING: ApproachingStopDetection



[1/2]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Approach_88

Movement State: between_stops

Matched Segment: 162_679

Segment Progress: 0.7455517361366206

Route Progress: 0.0140670138893702

Current Stop: None

Next Stop: 679

Distance To Next Stop: 174.38190828843665

Events: None

==========================================

----------------------------------------

[2/2]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Approach_88

Movement State: approaching_stop

Matched Segment: 162_679

Segment Progress: 0.9197453396436839

Route Progress: 0.015710349771512307

Current Stop: None

Next Stop: 679

Distance To Next Stop: 55.0010901226857

Events: None

}

Test Case 3 — Stop Arrival Detection



This validates:



distance <= 40

speed <= 5



Input speed:



"speed": 0



or



"speed": 3



Expected:



Check	Result

Stop radius condition satisfied	PASS

Low speed detected	PASS

movement_state = at_stop	PASS

current_stop_id assigned	PASS



Evidence:



Logs:



DISTANCE TO NEXT STOP: <40

STATE: at_stop



DB:



movement_state = at_stop

current_stop_id != null

test set:{{

"scenario_name": "StopArrivalDetection_Run02",

"vehicle_id": "V_Engine_Arrival_02_Final",

"expected_behavior": [

"between_stops",

"approaching_stop",

"at_stop"

],

"observations": [

{

"vehicle_id": "V_Engine_Arrival_02_Final2",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T19:50:00",

"lat": 30.0301356,

"lon": 31.2402126,

"speed": 34.0,

"bearing": 56

},

{

"vehicle_id": "V_Engine_Arrival_02_Final2",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T19:50:20",

"lat": 30.0314731,

"lon": 31.2421675,

"speed": 22.0,

"bearing": 57

},

{

"vehicle_id": "V_Engine_Arrival_02_Final2",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T19:50:40",

"lat": 30.0320463,

"lon": 31.2430053,

"speed": 1.5,

"bearing": 58

}

]

}}, output:RUNNING: StopArrivalDetection_Run02



[1/3]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Arrival_02_Final2

Movement State: between_stops

Matched Segment: 162_679

Segment Progress: 0.4999992565509095

Route Progress: 0.009433948236809613

Current Stop: None

Next Stop: 679

Distance To Next Stop: 342.6682364836757

Events: None

==========================================

----------------------------------------

[2/3]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Arrival_02_Final2

Movement State: approaching_stop

Matched Segment: 162_679

Segment Progress: 0.8499958644566339

Route Progress: 0.01273580302837305

Current Stop: None

Next Stop: 679

Distance To Next Stop: 102.80272535157576

Events: None

==========================================

----------------------------------------

[3/3]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Arrival_02_Final2

Movement State: at_stop

Matched Segment: 162_679

Segment Progress: 0.9999914766111331

Route Progress: 0.015801783369008535

Current Stop: 679

Next Stop: 679

Distance To Next Stop: 0.005841346010789143

Events: None

Test Case 4 — Departure Transition Validation



This proves lifecycle logic.



Your code requires:



previous_state == at_stop



speed > 7



segment_progress > 0.08



Expected:



Flow:



at_stop

    |

    v

leaving_stop



Expected:



Check	Result

Previous state loaded	PASS

Departure speed detected	PASS

Movement away detected	PASS

leaving_stop generated	PASS



Evidence:



Logs:



previous_state: at_stop

STATE: leaving_stop



DB:



movement_state = leaving_stop , test set :{

"scenario_name": "DepartureTransitionValidation_Run04",

"vehicle_id": "V_Engine_Depart_04_Final",

"expected_behavior": [

"at_stop",

"at_stop",

"leaving_stop",

"starting_stop_id: 1994",

"next_stop_id: 1336",

"segment_id: 1994_1336"

],

"observations": [

{

"vehicle_id": "V_Engine_Depart_04_Final2",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T21:20:00",

"lat": 30.03323,

"lon": 31.2456876,

"speed": 0.0,

"bearing": 42

},

{

"vehicle_id": "V_Engine_Depart_04_Final2",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T21:20:15",

"lat": 30.03323,

"lon": 31.2456876,

"speed": 3.0,

"bearing": 42

},

{

"vehicle_id": "V_Engine_Depart_04_Final2",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T21:20:45",

"lat": 30.03358,

"lon": 31.2461,

"speed": 16.5,

"bearing": 42

},

{

"vehicle_id": "V_Engine_Depart_04_Final2",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T21:21:10",

"lat": 30.0340,

"lon": 31.24655,

"speed": 18.0,

"bearing": 42

}

]

}, output :

[1/4]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Depart_04_Final2

Movement State: at_stop

Matched Segment: 679_1994

Segment Progress: 1

Route Progress: 0.03773584905660377

Current Stop: 1994

Next Stop: 1994

Distance To Next Stop: 0.0

Events: None

==========================================

----------------------------------------

[2/4]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Depart_04_Final2

Movement State: at_stop

Matched Segment: 679_1994

Segment Progress: 1

Route Progress: 0.03773584905660377

Current Stop: 1994

Next Stop: 1994

Distance To Next Stop: 0.0

Events: None

==========================================

----------------------------------------

[3/4]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Depart_04_Final2

Movement State: at_stop

Matched Segment: 1994_1336

Segment Progress: 0.1529147417201293

Route Progress: 0.03917844095962386

Current Stop: 1336

Next Stop: 1336

Distance To Next Stop: 311.10262160503106

Events: None

==========================================

----------------------------------------

[4/4]

========== VEHICLE STATE RESULT ==========

Vehicle: V_Engine_Depart_04_Final2

Movement State: leaving_stop

Matched Segment: 1994_1336

Segment Progress: 0.3279905866643059

Route Progress: 0.04155139582570161

Current Stop: None

Next Stop: 1336

Distance To Next Stop: 246.80362681117722

Events: None,

Test Case 5 — GPS Noise / False Transition Prevention



This is the most academically valuable one.



It proves Chapter 4:



transition validation and lifecycle awareness



Scenario:



Vehicle is traveling normally.



Then one noisy observation:



close-ish to stop

low speed

but no stable evidence



Expected:



Wrong old behavior:



between_stops

      |

      v

at_stop ❌



New behavior:



between_stops

      |

      v

between_stops ✅



Expected:



Check	Result

Temporary condition detected	PASS

Transition not immediately accepted	PASS

Previous movement maintained	PASS



Evidence:



Logs:



previous_state: between_stops

candidate transition rejected

STATE: between_stops



DB:



state remains:



between_stops, test set :{

"scenario_name": "GPSNoiseTransitionProtection_Run03",

"vehicle_id": "V_Engine_Noise_03_Final",

"expected_behavior": [

"between_stops",

"between_stops",

"between_stops",

"between_stops"

],

"observations": [

{

"vehicle_id": "V_Engine_Noise_03_Final",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T22:30:00",

"lat": 30.0287981,

"lon": 31.2382577,

"speed": 24.5,

"bearing": 55

},

{

"vehicle_id": "V_Engine_Noise_03_Final",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T22:30:20",

"lat": 30.0301356,

"lon": 31.2402126,

"speed": 28.0,

"bearing": 56

},

{

"vehicle_id": "V_Engine_Noise_03_Final",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T22:30:40",

"lat": 30.0311221,

"lon": 31.2415512,

"speed": 2.0,

"bearing": 56

},

{

"vehicle_id": "V_Engine_Noise_03_Final",

"route_id": "CTA_M_112",

"direction": 0,

"timestamp": "2026-06-18T22:31:00",

"lat": 30.0314731,

"lon": 31.2421675,

"speed": 19.5,

"bearing": 57

}

]

}, output :[1/4] ========== VEHICLE STATE RESULT ========== Vehicle: V_Engine_Noise_03_Final Movement State: between_stops Matched Segment: 162_679 Segment Progress: 0.15000264864488877 Route Progress: 0.002830238653677147 Current Stop: None Next Stop: 679 Distance To Next Stop: 582.535740005377 Events: None ========================================== ---------------------------------------- [2/4] ========== VEHICLE STATE RESULT ========== Vehicle: V_Engine_Noise_03_Final Movement State: between_stops Matched Segment: 162_679 Segment Progress: 0.4999992565509095 Route Progress: 0.00613209344524338 Current Stop: None Next Stop: 679 Distance To Next Stop: 342.6682364836757 Events: None ========================================== ---------------------------------------- [3/4] ========== VEHICLE STATE RESULT ========== Vehicle: V_Engine_Noise_03_Final Movement State: between_stops Matched Segment: 162_679 Segment Progress: 0.7455517361366206 Route Progress: 0.01009955366730679 Current Stop: None Next Stop: 679 Distance To Next Stop: 174.38190828843665 Events: None ========================================== ---------------------------------------- [4/4] ========== VEHICLE STATE RESULT ========== Vehicle: V_Engine_Noise_03_Final Movement State: approaching_stop Matched Segment: 162_679 Segment Progress: 0.8499958644566339 Route Progress: 0.013068605743621639 Current Stop: None Next Stop: 679 Distance To Next Stop: 102.80272535157576 Events: None

note regarding test set 5 :you said "Your real expected behavior should be updated to:



"expected_behavior": [

    "between_stops",

    "between_stops",

    "between_stops",

    "approaching_stop"

]



And describe it as:



The vehicle experiences a temporary low-speed observation while still outside the stop radius. The Vehicle State Engine prevents a false stop arrival and maintains traversal continuity until valid approach conditions are detected."







Change 6 — segment_start_time

Status:

NOT DONE ❌

Needed by:

current_delay
maybe debugging labels

Decision already made:

No DB change.

Compute:

vehicle route_CTA_80
segment 100_101

snapshots:

08:00 progress 0.02  ← segment_start
08:01 progress 0.2
08:02 progress 0.5

Use first timestamp.

Change 7 — remaining_time label

Status:

NOT DONE ❌

This is the biggest remaining part.

Need new loader:

Something like:

load_segment_completions()

gets:

vehicle_id
segment_id
completion_timestamp
travel_time

from:

transit_events
WHERE event_type='segment_completed'

Then:

for each state:

remaining_time =
completion_time - state_timestamp