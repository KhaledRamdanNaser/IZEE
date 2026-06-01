(venv) PS C:\Users\mohamed\IZEE> uvicorn main:app --reload
INFO:     Will watch for changes in these directories: ['C:\\Users\\mohamed\\IZEE']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)       
INFO:     Started reloader process [19512] using StatReload
INFO:     Started server process [33364]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '162_679', 'start': {'stop_id': '162', 'lat': 30.028224865740217, 'lon': 31.23741986574023, 'sequence': 1}, 'end': {'stop_id': '679', 'lat': 30.032046321339188, 'lon': 31.243005355292347, 'sequence': 2}}     
DISTANCE TO NEXT STOP: 685.3395201165898
NEXT STOP: 679
---- DETECTOR DEBUG ----
previous_state: None
current_state: {'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-05-28T18:00:00', 'matched_position': {'lat': 30.028224865740217, 'lon': 31.23741986574023}, 'current_stop_id': None, 'next_stop_id': '679', 'stop_sequence': 2, 'segment_id': '162_679', 'segment_progress': 0, 'progress': 0.0, 'distance_to_next_stop': 685.3395201165898, 'speed': 0.0, 'direction': 'unknown', 'movement': 'stopped', 'movement_state': 'between_stops', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: None
curr_state: between_stops
PREV STOP_SEQ: None
CURR STOP_SEQ: 2
EVENTS: []
FINAL EVENTS: []
STATE: between_stops
EVENTS STAGED: 0
DB NEW OBJECTS: 1
INFO:     127.0.0.1:53694 - "POST /vehicle/location HTTP/1.1" 200 OK
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '162_679', 'start': {'stop_id': '162', 'lat': 30.028224865740217, 'lon': 31.23741986574023, 'sequence': 1}, 'end': {'stop_id': '679', 'lat': 30.032046321339188, 'lon': 31.243005355292347, 'sequence': 2}}     
DISTANCE TO NEXT STOP: 582.535740005377
NEXT STOP: 679
---- DETECTOR DEBUG ----
previous_state: {'progress': 0.0, 'movement_state': 'between_stops', 'next_stop_id': '679', 'stop_sequence': 2, 'current_delay': 0.0}
current_state: {'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-05-28T18:00:45', 'matched_position': {'lat': 30.02879809420174, 'lon': 31.238257703967026}, 'current_stop_id': None, 'next_stop_id': '679', 'stop_sequence': 2, 'segment_id': '162_679', 'segment_progress': 0.15000264864488877, 'progress': 0.0014151193268385734, 'distance_to_next_stop': 582.535740005377, 'speed': 15.0, 'direction': 'forward', 'movement': 'moving', 'movement_state': 'between_stops', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: between_stops
curr_state: between_stops
BOOTSTRAP: traversal lifecycle initialized
PREV STOP_SEQ: 2
CURR STOP_SEQ: 2
EVENTS: []
FINAL EVENTS: []
STATE: between_stops
EVENTS STAGED: 0
DB NEW OBJECTS: 0
INFO:     127.0.0.1:53696 - "POST /vehicle/location HTTP/1.1" 200 OK
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '162_679', 'start': {'stop_id': '162', 'lat': 30.028224865740217, 'lon': 31.23741986574023, 'sequence': 1}, 'end': {'stop_id': '679', 'lat': 30.032046321339188, 'lon': 31.243005355292347, 'sequence': 2}}     
DISTANCE TO NEXT STOP: 342.6682364836757
NEXT STOP: 679
---- DETECTOR DEBUG ----
previous_state: {'progress': 0.0014151193268385734, 'movement_state': 'between_stops', 'next_stop_id': '679', 'stop_sequence': 2, 'current_delay': 0.0}
current_state: {'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-05-28T18:01:30', 'matched_position': {'lat': 30.030135590698645, 'lon': 31.240212606363762}, 'current_stop_id': None, 'next_stop_id': '679', 'stop_sequence': 2, 'segment_id': '162_679', 'segment_progress': 0.4999992565509095, 'progress': 0.005424533781824094, 'distance_to_next_stop': 342.6682364836757, 'speed': 36.0, 'direction': 'forward', 'movement': 'moving', 'movement_state': 'between_stops', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: between_stops
curr_state: between_stops
PREV STOP_SEQ: 2
CURR STOP_SEQ: 2
EVENTS: []
FINAL EVENTS: []
STATE: between_stops
EVENTS STAGED: 0
DB NEW OBJECTS: 0
INFO:     127.0.0.1:53697 - "POST /vehicle/location HTTP/1.1" 200 OK
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '162_679', 'start': {'stop_id': '162', 'lat': 30.028224865740217, 'lon': 31.23741986574023, 'sequence': 1}, 'end': {'stop_id': '679', 'lat': 30.032046321339188, 'lon': 31.243005355292347, 'sequence': 2}}     
DISTANCE TO NEXT STOP: 139.23650461216445
NEXT STOP: 679
---- DETECTOR DEBUG ----
previous_state: {'progress': 0.005424533781824094, 'movement_state': 'between_stops', 'next_stop_id': '679', 'stop_sequence': 2, 'current_delay': 0.0}
current_state: {'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-05-28T18:02:10', 'matched_position': {'lat': 30.031269930753638, 'lon': 31.241870572644313}, 'current_stop_id': None, 'next_stop_id': '679', 'stop_sequence': 2, 'segment_id': '162_679', 'segment_progress': 0.796833807055647, 'progress': 0.010229566957474755, 'distance_to_next_stop': 139.23650461216445, 'speed': 22.0, 'direction': 'forward', 'movement': 'moving', 'movement_state': 'approaching_stop', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: between_stops
curr_state: approaching_stop
PREV STOP_SEQ: 2
CURR STOP_SEQ: 2
EVENTS: []
FINAL EVENTS: []
STATE: approaching_stop
EVENTS STAGED: 0
DB NEW OBJECTS: 0
INFO:     127.0.0.1:53698 - "POST /vehicle/location HTTP/1.1" 200 OK
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '162_679', 'start': {'stop_id': '162', 'lat': 30.028224865740217, 'lon': 31.23741986574023, 'sequence': 1}, 'end': {'stop_id': '679', 'lat': 30.032046321339188, 'lon': 31.243005355292347, 'sequence': 2}}     
DISTANCE TO NEXT STOP: 55.0010901226857
NEXT STOP: 679
---- DETECTOR DEBUG ----
previous_state: {'progress': 0.010229566957474755, 'movement_state': 'approaching_stop', 'next_stop_id': '679', 'stop_sequence': 2, 'current_delay': 0.0}       
current_state: {'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-05-28T18:02:35', 'matched_position': {'lat': 30.031739631718025, 'lon': 31.242557093725416}, 'current_stop_id': None, 'next_stop_id': '679', 'stop_sequence': 2, 'segment_id': '162_679', 'segment_progress': 0.9197453396436839, 'progress': 0.013791626305564584, 'distance_to_next_stop': 55.0010901226857, 'speed': 10.0, 'direction': 'forward', 'movement': 'moving', 'movement_state': 'approaching_stop', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: approaching_stop
curr_state: approaching_stop
PREV STOP_SEQ: 2
CURR STOP_SEQ: 2
EVENTS: []
FINAL EVENTS: []
STATE: approaching_stop
EVENTS STAGED: 0
DB NEW OBJECTS: 0
INFO:     127.0.0.1:53700 - "POST /vehicle/location HTTP/1.1" 200 OK
ROUTE: CTA_M_112
MATCHED SEGMENT: {'segment_id': '162_679', 'start': {'stop_id': '162', 'lat': 30.028224865740217, 'lon': 31.23741986574023, 'sequence': 1}, 'end': {'stop_id': '679', 'lat': 30.032046321339188, 'lon': 31.243005355292347, 'sequence': 2}}     
DISTANCE TO NEXT STOP: 0.005841346010789143
NEXT STOP: 679
---- DETECTOR DEBUG ----
previous_state: {'progress': 0.013791626305564584, 'movement_state': 'approaching_stop', 'next_stop_id': '679', 'stop_sequence': 2, 'current_delay': 0.0}       
current_state: {'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'trip_id': None, 'timestamp': '2026-05-28T18:03:00', 'matched_position': {'lat': 30.032046288767436, 'lon': 31.243005307685046}, 'current_stop_id': '679', 
'next_stop_id': '679', 'stop_sequence': 2, 'segment_id': '162_679', 'segment_progress': 0.9999914766111331, 'progress': 0.0163296950076043, 'distance_to_next_stop': 0.005841346010789143, 'speed': 0.0, 'direction': 'forward', 'movement': 'stopped', 'movement_state': 'at_stop', 'current_delay': 0, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}
prev_state: approaching_stop
curr_state: at_stop
✅ ARRIVAL CONDITION TRIGGERED
PREV STOP_SEQ: 2
CURR STOP_SEQ: 2
EVENTS: [{'event_id': '1d270a55-34dd-4b05-8415-801a848bc4ba', 'event_type': 'stop_arrival', 'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'timestamp': '2026-05-28T18:03:00', 'stop_id': '679', 'from_stop_id': None, 'to_stop_id': None, 'segment_id': None, 'stop_sequence': 2, 'metrics': {}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}, {'event_id': '30cb04a5-5b25-4799-a100-f9c044b084a9', 'event_type': 'segment_completed', 'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'timestamp': '2026-05-28T18:03:00', 'stop_id': None, 'from_stop_id': '162', 'to_stop_id': '679', 'segment_id': '162_679', 'stop_sequence': 2, 'metrics': {'travel_time': 135.0}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}]
FINAL EVENTS: [{'event_id': '1d270a55-34dd-4b05-8415-801a848bc4ba', 'event_type': 'stop_arrival', 'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'timestamp': '2026-05-28T18:03:00', 'stop_id': '679', 'from_stop_id': None, 'to_stop_id': None, 'segment_id': None, 'stop_sequence': 2, 'metrics': {}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}, {'event_id': '30cb04a5-5b25-4799-a100-f9c044b084a9', 'event_type': 'segment_completed', 'vehicle_id': 'BusEE_HappyPath_Test_Run01', 'route_id': 'CTA_M_112', 'timestamp': '2026-05-28T18:03:00', 'stop_id': None, 'from_stop_id': '162', 'to_stop_id': '679', 'segment_id': '162_679', 'stop_sequence': 2, 'metrics': {'travel_time': 135.0}, 'confidence': 'medium', 'source': 'simulated', 'simulation_flag': True}]   
STATE: at_stop
ADDING EVENT: stop_arrival
ADDING EVENT: segment_completed
EVENTS STAGED: 2
DB NEW OBJECTS: 2
INFO:     127.0.0.1:53702 - "POST /vehicle/location HTTP/1.1" 200 OK
