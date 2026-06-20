import pandas as pd

gtfs_dir = r"C:\Users\omaro\Documents\IZEE UI\link (7)"

try:
    routes_df = pd.read_csv(f"{gtfs_dir}/routes.txt")
    print("--- Searching route names for 1023 or Route 8 ---")
    
    # search short name or long name
    match_1023 = routes_df[
        routes_df['route_id'].astype(str).str.contains('1023') |
        routes_df['route_short_name'].astype(str).str.contains('1023') |
        routes_df['route_long_name'].astype(str).str.contains('1023')
    ]
    print(f"Matches for '1023': {len(match_1023)}")
    if not match_1023.empty:
        print(match_1023[['route_id', 'route_short_name', 'route_long_name']])
        
    match_8 = routes_df[
        routes_df['route_id'].astype(str).str.match('^8$|^Route 8$') |
        routes_df['route_short_name'].astype(str).str.match('^8$|^Route 8$') |
        routes_df['route_long_name'].astype(str).str.match('^8$|^Route 8$')
    ]
    print(f"Exact matches for '8' or 'Route 8': {len(match_8)}")
    if not match_8.empty:
        print(match_8[['route_id', 'route_short_name', 'route_long_name']])
        
    # Check if there is any shape_id in trips.txt that starts with CTA or similar
    trips_df = pd.read_csv(f"{gtfs_dir}/trips.txt")
    print(f"Total trips: {len(trips_df)}")
    print("Sample shape_ids in trips:")
    print(trips_df['shape_id'].dropna().unique()[:20])

except Exception as e:
    print(f"Error: {e}")
