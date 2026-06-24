import os
import csv
import re
import json

CSV_PATH = r"C:\Users\omaro\Desktop\semeser 8\result (2).csv"
JS_OUTPUT_PATH = r"C:\Users\omaro\Desktop\semeser 8\control_center_dashboard\survey_data.js"

# Bounding box for Greater Cairo region
LAT_MIN = 29.80
LAT_MAX = 30.30
LON_MIN = 30.90
LON_MAX = 31.60

# Centroids of major Cairo districts
NEIGHBORHOODS = [
    {"name": "Downtown Cairo", "lat": 30.0444, "lon": 31.2357},
    {"name": "Giza", "lat": 29.9870, "lon": 31.2118},
    {"name": "Heliopolis", "lat": 30.1000, "lon": 31.3300},
    {"name": "Nasr City", "lat": 30.0550, "lon": 31.3450},
    {"name": "Maadi", "lat": 29.9700, "lon": 31.2650},
    {"name": "Zamalek", "lat": 30.0650, "lon": 31.2200},
    {"name": "Mohandessin", "lat": 30.0600, "lon": 31.2000},
    {"name": "Shobra", "lat": 30.0900, "lon": 31.2450},
    {"name": "El-Marg & Salam", "lat": 30.1550, "lon": 31.3250},
    {"name": "New Cairo (Tagamoa)", "lat": 30.0250, "lon": 31.4750},
    {"name": "Helwan", "lat": 29.8400, "lon": 31.3300},
    {"name": "6th of October", "lat": 29.9600, "lon": 30.9300},
]

def is_inside_bounds(lat, lon):
    return (LAT_MIN <= lat <= LAT_MAX) and (LON_MIN <= lon <= LON_MAX)

def get_neighborhood_name(lat, lon):
    min_dist = float("inf")
    closest_name = "Cairo"
    for n in NEIGHBORHOODS:
        dist = (lat - n["lat"])**2 + (lon - n["lon"])**2
        if dist < min_dist:
            min_dist = dist
            closest_name = n["name"]
    return closest_name

def parse_wkt_point(point_str):
    # Parses POINT (31.3246 30.1002)
    match = re.match(r"POINT\s*\(([^ ]+)\s+([^ ]+)\)", point_str.strip())
    if match:
        return float(match.group(1)), float(match.group(2))
    return None

def clean_age(age_str):
    age_str = age_str.strip()
    if not age_str or age_str.lower() in ("no_answer", "no answer", "nan", "null"):
        return "no_answer"
    try:
        val = float(age_str)
        if 18 <= val <= 25:
            return "18-25"
        elif 26 <= val <= 35:
            return "26-35"
        elif 36 <= val <= 45:
            return "36-45"
        elif 46 <= val <= 55:
            return "46-55"
        elif 56 <= val <= 65:
            return "56-65"
        elif 66 <= val <= 75:
            return "66-75"
        elif val > 75:
            return ">75"
        elif val < 18:
            return "<18"
    except ValueError:
        pass
    return age_str

def process():
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    mode_split = {}
    hourly_purpose = {f"{h:02d}:00": {} for h in range(24)}
    demographics = {
        "gender": {},
        "age": {},
        "income": {}
    }
    
    all_rows = []

    print("Parsing CSV...")
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_rows.append(row)

            # 1. Mode split (comma separated lists parsed individually)
            modes = [m.strip() for m in row["mode"].split(",")]
            for mode in modes:
                if mode:
                    mode_split[mode] = mode_split.get(mode, 0) + 1

            # 2. Hourly purpose
            time_str = row["survey_time"]
            purpose = row["trip_purpose"] or "other"
            if time_str:
                hour = time_str.split(":")[0]
                if hour.isdigit():
                    h_key = f"{int(hour):02d}:00"
                    if h_key in hourly_purpose:
                        hourly_purpose[h_key][purpose] = hourly_purpose[h_key].get(purpose, 0) + 1

            # 3. Demographics
            g = row["gender"] or "no_answer"
            demographics["gender"][g] = demographics["gender"].get(g, 0) + 1

            a = clean_age(row["age"])
            demographics["age"][a] = demographics["age"].get(a, 0) + 1

            inc = row["income"] or "no_answer"
            demographics["income"][inc] = demographics["income"].get(inc, 0) + 1

    # Filter and sample up to 100 trips inside Cairo bounds for the map
    # (100 is optimal to prevent map polyline overlap while remaining rich)
    hotspots = []
    
    for row in all_rows:
        origin_pt = parse_wkt_point(row["origin"])
        dest_pt = parse_wkt_point(row["destination"])
        
        if origin_pt and dest_pt:
            o_lon, o_lat = origin_pt
            d_lon, d_lat = dest_pt
            
            # Check if both start and end fall inside the visible Cairo bounds
            if is_inside_bounds(o_lat, o_lon) and is_inside_bounds(d_lat, d_lon):
                hotspots.append({
                    "origin": {"lat": o_lat, "lon": o_lon, "name": get_neighborhood_name(o_lat, o_lon)},
                    "destination": {"lat": d_lat, "lon": d_lon, "name": get_neighborhood_name(d_lat, d_lon)},
                    "purpose": row["trip_purpose"] or "other",
                    "mode": row["mode"].replace("_", " ").title()
                })

    # Sample exactly 100 trips evenly spaced from the valid Cairo trips
    total_valid = len(hotspots)
    sampled_trips = []
    if total_valid > 0:
        step = max(1, total_valid // 100)
        for idx in range(0, total_valid, step):
            if len(sampled_trips) >= 100:
                break
            sampled_trips.append(hotspots[idx])

    output_data = {
        "total_records": len(all_rows),
        "mode_split": mode_split,
        "hourly_purpose": hourly_purpose,
        "demographics": demographics,
        "hotspots": sampled_trips
    }

    print(f"Writing survey aggregated data to {JS_OUTPUT_PATH}...")
    with open(JS_OUTPUT_PATH, "w", encoding="utf-8") as out:
        out.write("/* Generated automatically from result (2).csv */\n")
        out.write("window.SURVEY_DATA = ")
        out.write(json.dumps(output_data, indent=2))
        out.write(";\n")
    print("Done!")

if __name__ == "__main__":
    process()
