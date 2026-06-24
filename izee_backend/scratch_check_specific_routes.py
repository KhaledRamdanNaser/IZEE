import pandas as pd

gtfs_dir = r"C:\Users\omaro\Desktop\semeser 8\link (7)"

try:
    routes_df = pd.read_csv(f"{gtfs_dir}/routes.txt")
    print("--- Searching for specific route IDs ---")
    for r_id in ["Route 8", "CTA 1023", "Route 15", "A-12 Express"]:
        match = routes_df[routes_df['route_id'] == r_id]
        if not match.empty:
            print(f"Exact match found for '{r_id}':")
            print(match)
        else:
            # Try case insensitive or substring search
            sub_match = routes_df[routes_df['route_id'].astype(str).str.lower().str.contains(r_id.lower().replace(" ", ""), na=False)]
            if not sub_match.empty:
                print(f"Substring matches for '{r_id}':")
                print(sub_match[['route_id', 'route_short_name', 'route_long_name']])
            else:
                print(f"No match found for '{r_id}'")
except Exception as e:
    print(f"Error: {e}")
