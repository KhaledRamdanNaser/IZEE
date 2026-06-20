from reference.loader import load_route_reference

route_id = "CTA_M_112"  # or any route you have

ref = load_route_reference(route_id)

print("ROUTE:", ref["route_id"])
print("STOPS:", len(ref["stops"]))
print("SEGMENTS:", len(ref["segments"]))

print("\nFirst stop:", ref["stops"][0])
print("First segment:", ref["segments"][0])