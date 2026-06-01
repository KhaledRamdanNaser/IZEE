from database.connection import SessionLocal
from reference.loader import load_route_reference
from vehicle_state.engine import process_observation
from event_engine.engine import process_event
from models.transit_event import TransitEvent
from models.vehicle_live_state import VehicleLiveState


route_cache = {}

last_transition_per_vehicle = {}

def process_observation_pipeline(
    observation,
    db_observation
):
    vehicle_id = observation["vehicle_id"]
    db = SessionLocal()
    try:

        route_id = observation["route_id"]
        direction_id=observation["direction"]
        cache_key = (
        route_id,
        direction_id
        )
        
        if cache_key not in route_cache:
            route_cache[cache_key] = load_route_reference(
                route_id,
                direction_id
            )

        route_reference = route_cache[cache_key]
        """

        if route_id not in route_cache:
            route_cache[route_id] = load_route_reference(route_id,direction_id)

        route_reference = route_cache[route_id]
        """

        print("ROUTE:", route_reference["route_id"])
        db.add(db_observation)

        # 1️⃣ Load previous state
        db_state = (
            db.query(VehicleLiveState)
            .filter(VehicleLiveState.vehicle_id == vehicle_id)
            .first()
        )

        previous_state = None

        if db_state:
            previous_state = {
                "progress": db_state.progress,
                "movement_state": db_state.movement_state,
                "next_stop_id": db_state.next_stop_id,
                "stop_sequence": db_state.stop_sequence,
                "current_delay": db_state.current_delay 
            }

        # 2️⃣ Process observation
        state = process_observation(
            observation,
            previous_state,
            route_reference
        )

        events = process_event(
            current_state=state,
            previous_state=previous_state,
            route_reference=route_reference
        )

        print("PREV STOP_SEQ:", previous_state.get("stop_sequence") if previous_state else None)
        print("CURR STOP_SEQ:", state.get("stop_sequence"))

        prev_seq = previous_state.get("stop_sequence") if previous_state else None
        curr_seq = state.get("stop_sequence")
        current_transition = (prev_seq, curr_seq)

        # 3️⃣ Filter duplicate transitions
        filtered_events = []
        last_transition = last_transition_per_vehicle.get(vehicle_id)

        for event in events:
            # 🔵 Apply duplicate filter ONLY for segment_travel
            if event["event_type"] == "segment_travel":
                if last_transition == current_transition:
                    print("IGNORED: duplicate transition", current_transition)
                    continue
            filtered_events.append(event)
        # Update only if segment event occurred
        if any(e["event_type"] == "segment_travel" for e in filtered_events):
            last_transition_per_vehicle[vehicle_id] = current_transition

        print("EVENTS:", filtered_events)

        
                                

        # 5️⃣ Merge events
        final_events = filtered_events 

        print("FINAL EVENTS:", final_events)
        print("STATE:", state["movement_state"])
        # 🔥 6️⃣ STORE EVENTS IN DB (ADD HERE)
        for event in final_events:
            print("ADDING EVENT:", event["event_type"])
            db_event = TransitEvent(
                
                event_id=event["event_id"],
                event_type=event["event_type"],
                vehicle_id=event["vehicle_id"],
                route_id=event["route_id"],
                timestamp=event["timestamp"],

                stop_id=event.get("stop_id"),
                from_stop_id=event.get("from_stop_id"),
                to_stop_id=event.get("to_stop_id"),
                segment_id=event.get("segment_id"),

                stop_sequence=event.get("stop_sequence"),

                metrics=event.get("metrics", {}),

                confidence=event.get("confidence"),
                source=event.get("source"),
                simulation_flag=event.get("simulation_flag")
            )
            db.add(db_event)
        event_count = sum(
            1
            for obj in db.new
            if isinstance(obj, TransitEvent)
        )

        print("EVENTS STAGED:", event_count)

        # 6️⃣ Update DB
        if db_state:
            db_state.route_id = state["route_id"]
            db_state.timestamp = state["timestamp"]
            db_state.matched_lat = state["matched_position"]["lat"]
            db_state.matched_lon = state["matched_position"]["lon"]
            db_state.current_stop_id = state["current_stop_id"]
            db_state.next_stop_id = state["next_stop_id"]
            db_state.stop_sequence = state["stop_sequence"]
            db_state.segment_id = state["segment_id"]
            db_state.segment_progress = state["segment_progress"]
            db_state.progress = state["progress"]
            db_state.distance_to_next_stop = state["distance_to_next_stop"]
            db_state.speed = state["speed"]
            db_state.direction = state["direction"]
            db_state.movement = state["movement"]
            db_state.movement_state = state["movement_state"]
            db_state.current_delay = state["current_delay"]
            db_state.confidence = state["confidence"]
            db_state.source = state["source"]
            db_state.simulation_flag = state["simulation_flag"]

        else:
            db_state = VehicleLiveState(
                vehicle_id=state["vehicle_id"],
                route_id=state["route_id"],
                timestamp=state["timestamp"],
                matched_lat=state["matched_position"]["lat"],
                matched_lon=state["matched_position"]["lon"],
                current_stop_id=state["current_stop_id"],
                next_stop_id=state["next_stop_id"],
                stop_sequence=state["stop_sequence"],
                segment_id=state["segment_id"],
                segment_progress=state["segment_progress"],
                progress=state["progress"],
                distance_to_next_stop=state["distance_to_next_stop"],
                speed=state["speed"],
                direction=state["direction"],
                movement=state["movement"],
                movement_state=state["movement_state"],
                current_delay=state["current_delay"],
                confidence=state["confidence"],
                source=state["source"],
                simulation_flag=state["simulation_flag"]
            )
            db.add(db_state)


        print(
    "DB NEW OBJECTS:",
    len(db.new)
     )
        db.commit()
    except Exception as e:
        db.rollback()
        print("PIPELINE ERROR:", e)
        raise
    finally:    
        db.close()

    return state

