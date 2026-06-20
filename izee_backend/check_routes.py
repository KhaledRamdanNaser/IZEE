from main import app

print("REGISTERED_VEHICLE_TRACKING_ROUTES:")
for route in app.routes:
    methods = getattr(route, "methods", "N/A")
    print(f"Path: {route.path} | Methods: {methods}")
