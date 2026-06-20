from simulation.observation_generator import stream_observations
from reference.loader import load_route_reference
from vehicle_state.engine import process_observation

print("TEST STARTED")

route = load_route_reference("CTA_M_112")

previous_state = None

for obs in stream_observations():
    state = process_observation(obs, previous_state, route)
    print(state)
    previous_state = state