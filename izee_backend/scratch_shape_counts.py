import pandas as pd

gtfs_dir = r"C:\Users\omaro\Desktop\semeser 8\link (7)"

try:
    shapes_df = pd.read_csv(f"{gtfs_dir}/shapes.txt")
    print("--- Shape IDs and Point Counts ---")
    counts = shapes_df['shape_id'].value_counts()
    print("Top 10 shape IDs by point count:")
    print(counts.head(10))
except Exception as e:
    print(f"Error: {e}")
