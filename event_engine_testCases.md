Event engine test cases 
Test set 1
:
 {
"scenario_name": "HappyPathFullTraversal",
"vehicle_id": "BusEE_HappyPath_Test_Run004",
"expected_behavior": [
"at_stop",
"stop_departure",
"between_stops",
"approaching_stop",
"at_stop",
"stop_arrival",
"segment_completed"
],
"observations": [
{
"vehicle_id": "BusEE_HappyPath_Test_Run004",
"route_id": "CTA_M_112",
"direction": 0,
"timestamp": "2026-05-28T21:00:00",
"lat": 30.0282248,
"lon": 31.2374198,
"speed": 0,
"bearing": 55
},
{
"vehicle_id": "BusEE_HappyPath_Test_Run004",
"route_id": "CTA_M_112",
"direction": 0,
"timestamp": "2026-05-28T21:00:45",
"lat": 30.0287981,
"lon": 31.2382577,
"speed": 15,
"bearing": 55
},
{
"vehicle_id": "BusEE_HappyPath_Test_Run004",
"route_id": "CTA_M_112",
"direction": 0,
"timestamp": "2026-05-28T21:01:30",
"lat": 30.0301356,
"lon": 31.2402126,
"speed": 36,
"bearing": 56
},
{
"vehicle_id": "BusEE_HappyPath_Test_Run004",
"route_id": "CTA_M_112",
"direction": 0,
"timestamp": "2026-05-28T21:02:10",
"lat": 30.0313000,
"lon": 31.2418500,
"speed": 22,
"bearing": 57
},
{
"vehicle_id": "BusEE_HappyPath_Test_Run004",
"route_id": "CTA_M_112",
"direction": 0,
"timestamp": "2026-05-28T21:02:35",
"lat": 30.0317500,
"lon": 31.2425500,
"speed": 10,
"bearing": 57
},
{
"vehicle_id": "BusEE_HappyPath_Test_Run004",
"route_id": "CTA_M_112",
"direction": 0,
"timestamp": "2026-05-28T21:03:00",
"lat": 30.0320463,
"lon": 31.2430053,
"speed": 0,
"bearing": 58
}
]
}

RUNNING: HappyPathFullTraversal

[1/6]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 685.3395201165898
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[2/6]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 582.535740005377
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[3/6]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 342.6682364836757
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[4/6]
========== VEHICLE STATE ==========
Movement State: approaching_stop
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 139.23650461216445
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[5/6]
========== VEHICLE STATE ==========
Movement State: approaching_stop
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 55.0010901226857
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[6/6]
========== VEHICLE STATE ==========
Movement State: at_stop
Segment: 162_679
Current Stop: 679
Next Stop: 679
Distance: 0.005841346010789143
========== EVENT ENGINE ==========
Event Count: 2

EVENT 1
Type: stop_arrival
Stop: 679
From: None
To: None
Segment: None
Metrics: {}

EVENT 2
Type: segment_completed
Stop: None
From: 162
To: 679
Segment: 162_679
Metrics: {'travel_time': 135.0, 'completion_method': 'stop_arrival'}

 


Test Set 2 : 


{
  "scenario_name": "DwellLifecycleValidation",
  "vehicle_id": "BusEE_Dwell_Final",
  "expected_behavior": [
    "vehicle begins already servicing operational stop",
    "stop_arrival emitted exactly once upon stop acquisition",
    "multiple stationary observations preserve stable at_stop ownership",
    "leaving_stop transition triggers clean stop_departure event",
    "dwell_time emitted exactly once during departure finalization",
    "post-departure traversal bootstrap initializes correctly"
  ],
  "observations": [
    {
      "vehicle_id": "BusEE_Dwell_Final002",
      "route_id": "CTA_M_112",
      "direction": 0,
      "timestamp": "2026-05-28T21:30:00",
      "lat": 30.0319500,
      "lon": 31.2429000,
      "speed": 2,
      "bearing": 58
    },
    {
      "vehicle_id": "BusEE_Dwell_Final002",
       "route_id": "CTA_M_112",
      "direction": 0,
      "timestamp": "2026-05-28T21:30:20",
      "lat": 30.0320463,
      "lon": 31.2430053,
      "speed": 0,
      "bearing": 58
    },
    {
      "vehicle_id": "BusEE_Dwell_Final002",
       "route_id": "CTA_M_112",
      "direction": 0,
      "timestamp": "2026-05-28T21:31:20",
      "lat": 30.0320463,
      "lon": 31.2430053,
      "speed": 0,
      "bearing": 58
    },
    {
      "vehicle_id": "BusEE_Dwell_Final002",
       "route_id": "CTA_M_112",
      "direction": 0,
      "timestamp": "2026-05-28T21:32:20",
      "lat": 30.0320463,
      "lon": 31.2430053,
      "speed": 0,
      "bearing": 58
    },
    {
      "vehicle_id": "BusEE_Dwell_Final002",
       "route_id": "CTA_M_112",
      "direction": 0,
      "timestamp": "2026-05-28T21:33:00",
      "lat": 30.0317000,
      "lon": 31.2425000,
      "speed": 10,
      "bearing": 238
    },
    {
      "vehicle_id": "BusEE_Dwell_Final002",
       "route_id": "CTA_M_112",
      "direction": 0,
      "timestamp": "2026-05-28T21:33:30",
      "lat": 30.0310000,
      "lon": 31.2414000,
      "speed": 22,
      "bearing": 238
    }
  ]
}

Output: (venv) PS C:\Users\mohamed\IZEE> python tests/run_scenario.py tests/scenarios/Dwell.json
RUNNING: DwellLifecycleValidation

[1/6]
========== VEHICLE STATE ==========
Movement State: at_stop
Segment: 162_679
Current Stop: 679
Next Stop: 679
Distance: 14.31300294392487
========== EVENT ENGINE ==========
Event Count: 1

EVENT 1
Type: stop_arrival
Stop: 679
From: None
To: None
Segment: None
Metrics: {}
==================================
----------------------------------------
[2/6]
========== VEHICLE STATE ==========
Movement State: at_stop
Segment: 162_679
Current Stop: 679
Next Stop: 679
Distance: 0.005841346010789143
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[3/6]
========== VEHICLE STATE ==========
Movement State: at_stop
Segment: 162_679
Current Stop: 679
Next Stop: 679
Distance: 0.005841346010789143
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[4/6]
========== VEHICLE STATE ==========
Movement State: at_stop
Segment: 162_679
Current Stop: 679
Next Stop: 679
Distance: 0.005841346010789143
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[5/6]
========== VEHICLE STATE ==========
Movement State: at_stop
Segment: 162_679
Current Stop: 679
Next Stop: 679
Distance: 62.038990358498374
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[6/6]
========== VEHICLE STATE ==========
Movement State: leaving_stop
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 194.0006308998845
========== EVENT ENGINE ==========
Event Count: 2

EVENT 1
Type: stop_departure
Stop: 679
From: None
To: None
Segment: None
Metrics: {}

EVENT 2
Type: dwell_time
Stop: 679
From: None
To: None
Segment: None
Metrics: {'dwell_time': 210.0}



Test Set 3:
{
"scenario_name": "CongestionTraversalPreservation",
"vehicle_id": "BusEE_Congestion_Final",
"expected_behavior": [
"between_stops remains stable during congestion",
"zero speed mid segment does not trigger fake at_stop",
"exactly one final segment_completed event emitted"
],
"observations": [
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:10:00",
"lat": 30.0282248,
"lon": 31.2374198,
"speed": 0,
"bearing": 55
},
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:10:45",
"lat": 30.0287981,
"lon": 31.2382577,
"speed": 20,
"bearing": 55
},
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:11:15",
"lat": 30.0294625,
"lon": 31.2392231,
"speed": 0,
"bearing": 56
},
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:12:15",
"lat": 30.0294625,
"lon": 31.2392231,
"speed": 0,
"bearing": 56
},
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:13:15",
"lat": 30.0294625,
"lon": 31.2392231,
"speed": 0,
"bearing": 56
},
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:14:00",
"lat": 30.0301356,
"lon": 31.2402126,
"speed": 30,
"bearing": 56
},
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:14:30",
"lat": 30.0313000,
"lon": 31.2418500,
"speed": 24,
"bearing": 57
},
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:14:55",
"lat": 30.0317500,
"lon": 31.2425500,
"speed": 12,
"bearing": 57
},
{
"vehicle_id": "BusEE_Congestion_Final1002",
 "route_id": "CTA_M_112",
      "direction": 0,
"timestamp": "2026-05-28T21:15:20",
"lat": 30.0320463,
"lon": 31.2430053,
"speed": 0,
"bearing": 58
}
]
}


RUNNING: CongestionTraversalPreservation

[1/9]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 685.3395201165898
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[2/9]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 582.535740005377
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[3/9]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 463.8575954761977
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[4/9]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 463.8575954761977
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[5/9]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 463.8575954761977
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[6/9]
========== VEHICLE STATE ==========
Movement State: between_stops
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 342.6682364836757
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[7/9]
========== VEHICLE STATE ==========
Movement State: approaching_stop
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 139.23650461216445
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[8/9]
========== VEHICLE STATE ==========
Movement State: approaching_stop
Segment: 162_679
Current Stop: None
Next Stop: 679
Distance: 55.0010901226857
========== EVENT ENGINE ==========
Event Count: 0
==================================
----------------------------------------
[9/9]
========== VEHICLE STATE ==========
Movement State: at_stop
Segment: 162_679
Current Stop: 679
Next Stop: 679
Distance: 0.005841346010789143
========== EVENT ENGINE ==========
Event Count: 2

EVENT 1
Type: stop_arrival
Stop: 679
From: None
To: None
Segment: None
Metrics: {}

EVENT 2
Type: segment_completed
Stop: None
From: 162
To: 679
Segment: 162_679
Metrics: {'travel_time': 275.0, 'completion_method': 'stop_arrival'}
