(venv) PS C:\Users\mohamed\IZEE> python tests/run_scenario.py tests/scenarios/DepartureTransitionValidation_Run04.json

RUNNING: DepartureTransitionValidation_Run04

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
Events: None
==========================================
----------------------------------------
INFO:     Application startup complete.
[TIMESTAMP NORMALIZED]
original: 2026-06-18 21:20:00
normalized: 2026-06-18 18:20:00
========== INGESTION TEST ==========
[VALIDATION PASSED]
vehicle_id: V_Engine_Depart_04_Final2
route_id: CTA_M_112
lat: 30.03323
lon: 31.2456876
speed: 0.0
bearing: 42.0
[TRANSIT OBSERVATION CREATED]
{'observation_id': 'ec77d7f3-a584-46d5-b272-bc082c875f29', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'direction': 0, 'timestamp': '2026-06-18T18:20:00', 'location': {'lat': 30.03323, 'lon': 31.2456876}, 'speed': 0.0, 'bearing': 42.0, 'source': 'simulated', 'simulation_flag': True, 'trust_level': 'medium', 'raw_payload': {'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'direction': 0, 'timestamp': '2026-06-18T21:20:00', 'lat': 30.03323, 'lon': 31.2456876, 'speed': 0.0, 'bearing': 42}, 'ingested_at': '2026-06-18T19:19:06.689897'}
[FORWARDING TO PROCESSING PIPELINE]
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '679_1994', 'start': {'stop_id': '679', 'lat': 30.032046321339188, 'lon': 31.243005355292347, 'sequence': 2}, 'end': {'stop_id': '1994', 'lat': 30.03323, 'lon': 31.2456876, 'sequence': 3}}
DISTANCE TO NEXT STOP: 0.0
NEXT STOP: 1994
---- DETECTOR DEBUG ----
previous_state: None
current_state: {'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-06-18T18:20:00', 'matched_position': {'lat': 30.03323, 'lon': 31.2456876}, 'current_stop_id': '1994', 'next_stop_id': '1994', 'stop_sequence': 3, 'segment_id': '679_1994', 'segment_progress': 1, 'progress': 0.03773584905660377, 'distance_to_next_stop': 0.0, 'speed': 0.0, 'direction': 'unknown', 'movement': 'stopped', 'movement_state': 'at_stop', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: None
curr_state: at_stop
✅ ARRIVAL CONDITION TRIGGERED
PREV STOP_SEQ: None
CURR STOP_SEQ: 3
EVENTS: [{'event_id': 'dc9274d7-c38e-40b5-a44e-bdd1d130a617', 'event_type': 'stop_arrival', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'timestamp': '2026-06-18T18:20:00', 'stop_id': '1994', 'from_stop_id': None, 'to_stop_id': None, 'segment_id': None, 'stop_sequence': 3, 'metrics': {}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}]
FINAL EVENTS: [{'event_id': 'dc9274d7-c38e-40b5-a44e-bdd1d130a617', 'event_type': 'stop_arrival', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'timestamp': '2026-06-18T18:20:00', 'stop_id': '1994', 'from_stop_id': None, 'to_stop_id': None, 'segment_id': None, 'stop_sequence': 3, 'metrics': {}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}]
STATE: at_stop
ADDING EVENT: stop_arrival
EVENTS STAGED: 1
DB NEW OBJECTS: 2
INFO:     127.0.0.1:62799 - "POST /vehicle/location HTTP/1.1" 200 OK
[TIMESTAMP NORMALIZED]
original: 2026-06-18 21:20:15
normalized: 2026-06-18 18:20:15
========== INGESTION TEST ==========
[VALIDATION PASSED]
vehicle_id: V_Engine_Depart_04_Final2
route_id: CTA_M_112
lat: 30.03323
lon: 31.2456876
speed: 3.0
bearing: 42.0
[TRANSIT OBSERVATION CREATED]
{'observation_id': '5fbbe0e6-f06d-4e94-ac63-ed27b163b635', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'direction': 0, 'timestamp': '2026-06-18T18:20:15', 'location': {'lat': 30.03323, 'lon': 31.2456876}, 'speed': 3.0, 'bearing': 42.0, 'source': 'simulated', 'simulation_flag': True, 'trust_level': 'medium', 'raw_payload': {'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'direction': 0, 'timestamp': '2026-06-18T21:20:15', 'lat': 30.03323, 'lon': 31.2456876, 'speed': 3.0, 'bearing': 42}, 'ingested_at': '2026-06-18T19:19:07.950802'}
[FORWARDING TO PROCESSING PIPELINE]
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '679_1994', 'start': {'stop_id': '679', 'lat': 30.032046321339188, 'lon': 31.243005355292347, 'sequence': 2}, 'end': {'stop_id': '1994', 'lat': 30.03323, 'lon': 31.2456876, 'sequence': 3}}
DISTANCE TO NEXT STOP: 0.0
NEXT STOP: 1994
---- DETECTOR DEBUG ----
previous_state: {'progress': 0.03773584905660377, 'movement_state': 'at_stop', 'next_stop_id': '1994', 'stop_sequence': 3, 'current_delay': 0.0}
current_state: {'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-06-18T18:20:15', 'matched_position': {'lat': 30.03323, 'lon': 31.2456876}, 'current_stop_id': '1994', 'next_stop_id': '1994', 'stop_sequence': 3, 'segment_id': '679_1994', 'segment_progress': 1, 'progress': 0.03773584905660377, 'distance_to_next_stop': 0.0, 'speed': 3.0, 'direction': 'unknown', 'movement': 'moving', 'movement_state': 'at_stop', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: at_stop
curr_state: at_stop
PREV STOP_SEQ: 3
CURR STOP_SEQ: 3
EVENTS: []
FINAL EVENTS: []
STATE: at_stop
EVENTS STAGED: 0
DB NEW OBJECTS: 0
INFO:     127.0.0.1:62802 - "POST /vehicle/location HTTP/1.1" 200 OK
[TIMESTAMP NORMALIZED]
original: 2026-06-18 21:20:45
normalized: 2026-06-18 18:20:45
========== INGESTION TEST ==========
[VALIDATION PASSED]
vehicle_id: V_Engine_Depart_04_Final2
route_id: CTA_M_112
lat: 30.03358
lon: 31.2461
speed: 16.5
bearing: 42.0
[TRANSIT OBSERVATION CREATED]
{'observation_id': '79100e08-5d5d-4eb8-8b58-f425c708241b', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'direction': 0, 'timestamp': '2026-06-18T18:20:45', 'location': {'lat': 30.03358, 'lon': 31.2461}, 'speed': 16.5, 'bearing': 42.0, 'source': 'simulated', 'simulation_flag': True, 'trust_level': 'medium', 'raw_payload': {'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'direction': 0, 'timestamp': '2026-06-18T21:20:45', 'lat': 30.03358, 'lon': 31.2461, 'speed': 16.5, 'bearing': 42}, 'ingested_at': '2026-06-18T19:19:08.984847'}
[FORWARDING TO PROCESSING PIPELINE]
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '1994_1336', 'start': {'stop_id': '1994', 'lat': 30.03323, 'lon': 31.2456876, 'sequence': 3}, 'end': {'stop_id': '1336', 'lat': 30.03586870200975, 'lon': 31.247982223657445, 'sequence': 4}}
DISTANCE TO NEXT STOP: 311.10262160503106
NEXT STOP: 1336
---- DETECTOR DEBUG ----
previous_state: {'progress': 0.03773584905660377, 'movement_state': 'at_stop', 'next_stop_id': '1994', 'stop_sequence': 3, 'current_delay': 0.0}
current_state: {'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-06-18T18:20:45', 'matched_position': {'lat': 30.0336334964363, 'lon': 31.246038481783923}, 'current_stop_id': '1336', 'next_stop_id': '1336', 'stop_sequence': 4, 'segment_id': '1994_1336', 'segment_progress': 0.1529147417201293, 'progress': 0.03917844095962386, 'distance_to_next_stop': 311.10262160503106, 'speed': 16.5, 'direction': 'forward', 'movement': 'moving', 'movement_state': 'at_stop', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: at_stop
curr_state: at_stop
PREV STOP_SEQ: 3
CURR STOP_SEQ: 4
EVENTS: [{'event_id': 'bff824da-047d-4d54-80de-caeaac38f46a', 'event_type': 'segment_travel', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'timestamp': '2026-06-18T18:20:45', 'stop_id': None, 'from_stop_id': '1994', 'to_stop_id': '1336', 'segment_id': None, 'stop_sequence': 4, 'metrics': {}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}]
FINAL EVENTS: [{'event_id': 'bff824da-047d-4d54-80de-caeaac38f46a', 'event_type': 'segment_travel', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'timestamp': '2026-06-18T18:20:45', 'stop_id': None, 'from_stop_id': '1994', 'to_stop_id': '1336', 'segment_id': None, 'stop_sequence': 4, 'metrics': {}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}]
STATE: at_stop
ADDING EVENT: segment_travel
EVENTS STAGED: 1
DB NEW OBJECTS: 1
INFO:     127.0.0.1:62803 - "POST /vehicle/location HTTP/1.1" 200 OK
[TIMESTAMP NORMALIZED]
original: 2026-06-18 21:21:10
normalized: 2026-06-18 18:21:10
========== INGESTION TEST ==========
[VALIDATION PASSED]
vehicle_id: V_Engine_Depart_04_Final2
route_id: CTA_M_112
lat: 30.034
lon: 31.24655
speed: 18.0
bearing: 42.0
[TRANSIT OBSERVATION CREATED]
{'observation_id': 'e3e1eda8-191d-4868-9b6c-9853c86b36a0', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'direction': 0, 'timestamp': '2026-06-18T18:21:10', 'location': {'lat': 30.034, 'lon': 31.24655}, 'speed': 18.0, 'bearing': 42.0, 'source': 'simulated', 'simulation_flag': True, 'trust_level': 'medium', 'raw_payload': {'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'direction': 0, 'timestamp': '2026-06-18T21:21:10', 'lat': 30.034, 'lon': 31.24655, 'speed': 18.0, 'bearing': 42}, 'ingested_at': '2026-06-18T19:19:10.000825'}
[FORWARDING TO PROCESSING PIPELINE]
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '1994_1336', 'start': {'stop_id': '1994', 'lat': 30.03323, 'lon': 31.2456876, 'sequence': 3}, 'end': {'stop_id': '1336', 'lat': 30.03586870200975, 'lon': 31.247982223657445, 'sequence': 4}}
DISTANCE TO NEXT STOP: 246.80362681117722
NEXT STOP: 1336
---- DETECTOR DEBUG ----
previous_state: {'progress': 0.03917844095962386, 'movement_state': 'at_stop', 'next_stop_id': '1336', 'stop_sequence': 4, 'current_delay': 0.0}
current_state: {'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-06-18T18:21:10', 'matched_position': {'lat': 30.034095469420212, 'lon': 31.24644021495958}, 'current_stop_id': None, 'next_stop_id': '1336', 'stop_sequence': 4, 'segment_id': '1994_1336', 'segment_progress': 0.3279905866643059, 'progress': 0.04155139582570161, 'distance_to_next_stop': 246.80362681117722, 'speed': 18.0, 'direction': 'forward', 'movement': 'moving', 'movement_state': 'leaving_stop', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: at_stop
curr_state: leaving_stop
🚪 DEPARTURE CONDITION TRIGGERED
PREV STOP_SEQ: 4
CURR STOP_SEQ: 4
EVENTS: [{'event_id': 'd1d7cf29-eccd-42a1-98dd-c0df7af598ca', 'event_type': 'stop_departure', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'timestamp': '2026-06-18T18:21:10', 'stop_id': '1336', 'from_stop_id': None, 'to_stop_id': None, 'segment_id': None, 'stop_sequence': 4, 'metrics': {}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}]
FINAL EVENTS: [{'event_id': 'd1d7cf29-eccd-42a1-98dd-c0df7af598ca', 'event_type': 'stop_departure', 'vehicle_id': 'V_Engine_Depart_04_Final2', 'route_id': 'CTA_M_112', 'timestamp': '2026-06-18T18:21:10', 'stop_id': '1336', 'from_stop_id': None, 'to_stop_id': None, 'segment_id': None, 'stop_sequence': 4, 'metrics': {}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}]
STATE: leaving_stop
ADDING EVENT: stop_departure
EVENTS STAGED: 1
DB NEW OBJECTS: 1