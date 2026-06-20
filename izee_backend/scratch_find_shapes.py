import os
import pandas as pd

workspace = r"C:\Users\omaro\Documents\IZEE UI"
shapes_files = []
for root, dirs, files in os.walk(workspace):
    for f in files:
        if f == "shapes.txt":
            shapes_files.append(os.path.join(root, f))

print("Found shapes.txt files:")
for path in shapes_files:
    print(f"\nPath: {path}")
    try:
        df = pd.read_csv(path)
        print(f"  Columns: {list(df.columns)}")
        print(f"  Number of rows: {len(df)}")
        print(f"  Unique shape_ids: {df['shape_id'].unique() if 'shape_id' in df.columns else 'none'}")
        print("  Sample:")
        print(df.head(2))
    except Exception as e:
        print(f"  Error reading file: {e}")
