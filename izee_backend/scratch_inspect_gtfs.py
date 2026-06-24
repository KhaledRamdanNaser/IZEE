import pandas as pd

gtfs_dir = r"C:\Users\omaro\Desktop\semeser 8\link (7)"

print("--- Inspecting GTFS link (7) ---")
try:
    routes_df = pd.read_csv(f"{gtfs_dir}/routes.txt")
    print(f"Total routes in GTFS: {len(routes_df)}")
    print("Sample routes:")
    print(routes_df[['route_id', 'route_short_name', 'route_long_name']].head(10))
    
    # Check if Route 8 or CTA 1023 is in routes.txt
    r8 = routes_df[routes_df['route_id'].astype(str).str.contains('8|CTA|1023', na=False)]
    print("\nMatching routes for '8' or 'CTA' or '1023':")
    print(r8)
except Exception as e:
    print(f"Error checking routes: {e}")

try:
    trips_df = pd.read_csv(f"{gtfs_dir}/trips.txt")
    print(f"\nTotal trips in GTFS: {len(trips_df)}")
    print("Trips columns:", list(trips_df.columns))
    
    # Sample trips
    print("Sample trips:")
    print(trips_df[['trip_id', 'route_id', 'shape_id']].head(5))
except Exception as e:
    print(f"Error checking trips: {e}")
