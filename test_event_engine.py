from event_engine.engine import process_event

# Simulate previous state
previous_state = {
    "vehicle_id": "bus_42",
    "route_id": 1,
    "timestamp": "2026-01-01T10:00:00",
    "movement_state": "approaching_stop",
    "next_stop_id": 679,
    "confidence": "high",
    "source": "simulated",
    "simulation_flag": True
}

# Simulate current state
current_state = {
    "vehicle_id": "bus_42",
    "route_id": 1,
    "timestamp": "2026-01-01T10:00:05",
    "movement_state": "at_stop",
    "next_stop_id": 679,
    "confidence": "high",
    "source": "simulated",
    "simulation_flag": True
}

# Run Event Engine
events = process_event(current_state, previous_state)

# Print results
print("Detected Events:")
for e in events:
    print(e)