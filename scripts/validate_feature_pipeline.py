import os
import sys
import pandas as pd
import numpy as np

def main():
    # 1. Load datasets
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    train_path = os.path.join(base_dir, 'scripts', 'feature_data', 'train_features.csv')
    test_path = os.path.join(base_dir, 'scripts', 'feature_data', 'test_features.csv')

    # Fallback paths
    if not os.path.exists(train_path):
        train_path = os.path.join('scripts', 'feature_data', 'train_features.csv')
        test_path = os.path.join('scripts', 'feature_data', 'test_features.csv')
    if not os.path.exists(train_path):
        train_path = os.path.join('feature_data', 'train_features.csv')
        test_path = os.path.join('feature_data', 'test_features.csv')

    if not os.path.exists(train_path) or not os.path.exists(test_path):
        print(f"ERROR: Datasets not found.\nExpected train at: {train_path}\nExpected test at:  {test_path}")
        sys.exit(1)

    try:
        train_df = pd.read_csv(train_path)
        test_df = pd.read_csv(test_path)
    except Exception as e:
        print(f"ERROR: Failed to load datasets: {e}")
        sys.exit(1)

    # 2. Validate schema consistency
    expected_cols = [
        "hour",
        "avg_segment_time",
        "current_delay",
        "day_of_week_encoded",
        "is_peak",
        "segment_id_encoded",
        "route_id_encoded",
        "std_travel_time",
        "stop_sequence",
        "segment_length_m",
        "travel_time",
    ]

    train_cols = list(train_df.columns)
    test_cols = list(test_df.columns)

    schema_mismatch = False
    if train_cols != test_cols:
        print("ERROR: Schema mismatch between TRAIN and TEST datasets.")
        print(f"  TRAIN columns: {train_cols}")
        print(f"  TEST columns:  {test_cols}")
        schema_mismatch = True

    # Check for missing feature columns
    missing_train = [c for c in expected_cols if c not in train_df.columns]
    missing_test = [c for c in expected_cols if c not in test_df.columns]

    if missing_train:
        print(f"ERROR: Expected columns missing in TRAIN: {missing_train}")
        schema_mismatch = True
    if missing_test:
        print(f"ERROR: Expected columns missing in TEST: {missing_test}")
        schema_mismatch = True

    if schema_mismatch:
        sys.exit(1)

    # 3. Validate missing values
    def check_missing(df, name):
        print(f"\nMissing value analysis for {name}:")
        has_fail = False
        total_rows = len(df)
        missing_counts = df.isnull().sum()
        
        for col in df.columns:
            cnt = missing_counts[col]
            pct = (cnt / total_rows * 100) if total_rows > 0 else 0.0
            print(f"  {col:<25} : {pct:>6.2f}% missing ({cnt}/{total_rows})")
            if pct > 5.0:
                has_fail = True
                
        total_cells = df.size
        total_missing = missing_counts.sum()
        total_pct = (total_missing / total_cells * 100) if total_cells > 0 else 0.0
        print(f"Total missing % for {name}: {total_pct:.2f}% ({total_missing}/{total_cells})")
        return has_fail

    train_missing_fail = check_missing(train_df, "TRAIN")
    test_missing_fail = check_missing(test_df, "TEST")

    missing_rate_ok = "NO" if (train_missing_fail or test_missing_fail) else "YES"

    # 4. Validate segment_length_m
    def validate_segment_length(df, name):
        print(f"\nsegment_length_m statistics for {name}:")
        col = "segment_length_m"
        s = df[col]
        
        s_min = s.min()
        s_max = s.max()
        s_mean = s.mean()
        s_median = s.median()
        s_std = s.std()
        
        total_rows = len(df)
        nan_count = s.isnull().sum()
        nan_pct = (nan_count / total_rows * 100) if total_rows > 0 else 0.0
        
        zero_count = (s == 0.0).sum()
        zero_pct = (zero_count / total_rows * 100) if total_rows > 0 else 0.0
        
        print(f"  Min: {s_min}")
        print(f"  Max: {s_max}")
        print(f"  Mean: {s_mean:.2f}")
        print(f"  Median: {s_median}")
        print(f"  Std: {s_std:.2f}")
        print(f"  % Zeros: {zero_pct:.2f}% ({zero_count}/{total_rows})")
        print(f"  % NaN: {nan_pct:.2f}% ({nan_count}/{total_rows})")
        
        is_ok = True
        if nan_count > 0:
            print(f"  FAIL: Column '{col}' contains NaN values!")
            is_ok = False
        if zero_pct > 5.0:
            print(f"  FAIL: Column '{col}' zero percentage ({zero_pct:.2f}%) exceeds 5% threshold!")
            is_ok = False
            
        return is_ok

    train_seg_ok = validate_segment_length(train_df, "TRAIN")
    test_seg_ok = validate_segment_length(test_df, "TEST")

    segment_length_ok = "YES" if (train_seg_ok and test_seg_ok) else "NO"

    # 5. Validate current_delay distribution shift
    print("\ncurrent_delay distribution shift check:")
    train_cd_mean = train_df["current_delay"].mean()
    test_cd_mean = test_df["current_delay"].mean()
    test_cd_std = test_df["current_delay"].std()

    print(f"  Train mean: {train_cd_mean:.4f}")
    print(f"  Test mean:  {test_cd_mean:.4f}")
    print(f"  Test std:   {test_cd_std:.4f}")

    if train_cd_mean > 5.0 * test_cd_mean and train_cd_mean > 1.0:
        print(f"  WARNING: Train mean(current_delay) is significantly greater than Test mean(current_delay) (expected but logged clearly).")
    elif train_cd_mean > test_cd_mean + 1.0:
        print(f"  WARNING: Train mean(current_delay) is greater than Test mean(current_delay) (expected but logged clearly).")

    # 6. Validate label distribution
    def validate_label(df, name):
        print(f"\nLabel (travel_time) distribution for {name}:")
        col = "travel_time"
        s = df[col]
        
        s_min = s.min()
        s_max = s.max()
        s_mean = s.mean()
        s_std = s.std()
        
        print(f"  Mean: {s_mean:.2f}")
        print(f"  Std:  {s_std:.2f}")
        print(f"  Min:  {s_min}")
        print(f"  Max:  {s_max}")
        
        if s_min < 0:
            print(f"  FAIL: Column '{col}' contains negative values: {s_min}")
            return False
            
        if s_min < 10 or s_max > 4000:
            print(f"  WARNING: travel_time min/max ({s_min}s / {s_max}s) is outside expected 10s -> 4000s range.")
            
        return True

    train_label_ok = validate_label(train_df, "TRAIN")
    test_label_ok = validate_label(test_df, "TEST")

    label_ok = "YES" if (train_label_ok and test_label_ok) else "NO"

    # 7. Check feature leakage risk
    print("\nFeature leakage and mismatch checks:")
    for col in train_df.columns:
        if col == "travel_time":
            continue
        if pd.api.types.is_numeric_dtype(train_df[col]) and pd.api.types.is_numeric_dtype(test_df[col]):
            train_all_zero = (train_df[col] == 0).all()
            test_all_zero = (test_df[col] == 0).all()
            if test_all_zero and not train_all_zero:
                print(f"  WARNING: Column '{col}' is constant zero in TEST, but not in TRAIN!")

    if "current_delay" in train_df.columns and "current_delay" in test_df.columns:
        train_cd_all_zero = (train_df["current_delay"] == 0).all()
        test_cd_all_zero = (test_df["current_delay"] == 0).all()
        if test_cd_all_zero and not train_cd_all_zero:
            print("  WARNING: 'current_delay' is constant zero in TEST but not in TRAIN. (Specifically flagged)")

    if "segment_id_encoded" in train_df.columns and "segment_id_encoded" in test_df.columns:
        train_unique_seg = set(train_df["segment_id_encoded"].unique())
        test_unique_seg = set(test_df["segment_id_encoded"].unique())
        overlap = len(train_unique_seg.intersection(test_unique_seg))
        total_test = len(test_unique_seg)
        overlap_pct = (overlap / total_test * 100) if total_test > 0 else 0.0
        print(f"  segment_id_encoded overlap: {overlap_pct:.2f}% of test segments are in train.")
        if overlap_pct < 80.0:
            print(f"  WARNING: segment_id_encoded distribution mismatch! Only {overlap_pct:.2f}% overlap of segment IDs in test.")

    if "avg_segment_time" in train_df.columns and "avg_segment_time" in test_df.columns:
        train_avg_mean = train_df["avg_segment_time"].mean()
        test_avg_mean = test_df["avg_segment_time"].mean()
        train_avg_std = train_df["avg_segment_time"].std()
        test_avg_std = test_df["avg_segment_time"].std()
        
        mean_diff_pct = abs(train_avg_mean - test_avg_mean) / train_avg_mean * 100 if train_avg_mean > 0 else 0.0
        std_diff_pct = abs(train_avg_std - test_avg_std) / train_avg_std * 100 if train_avg_std > 0 else 0.0
        
        print(f"  avg_segment_time mean: Train={train_avg_mean:.2f}, Test={test_avg_mean:.2f} (diff={mean_diff_pct:.2f}%)")
        if mean_diff_pct > 15.0:
            print(f"  WARNING: avg_segment_time mean mismatch! Diff is {mean_diff_pct:.2f}%")

    # Optional: Matplotlib plot
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 6))
        plt.hist(train_df['travel_time'], bins=50, alpha=0.5, label='TRAIN', density=True)
        plt.hist(test_df['travel_time'], bins=50, alpha=0.5, label='TEST', density=True)
        plt.title('travel_time Distribution (Train vs Test Overlay)')
        plt.xlabel('travel_time (seconds)')
        plt.ylabel('Density')
        plt.legend(loc='upper right')
        plt.grid(True, linestyle='--', alpha=0.5)
        
        output_dir = os.path.dirname(train_path)
        plot_path = os.path.join(output_dir, 'travel_time_distribution.png')
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"\nSaved travel_time distribution plot to: {plot_path}")
    except ImportError:
        print("\nNote: matplotlib is not installed. Skipping travel_time distribution plot.")
    except Exception as e:
        print(f"\nWarning: Failed to generate travel_time plot: {e}")

    # 8. Output final summary
    overall_status = "PASS" if (missing_rate_ok == "YES" and segment_length_ok == "YES" and label_ok == "YES") else "FAIL"

    print("\n========================")
    print("IZEE FEATURE VALIDATION")
    print("========================\n")
    print(f"TRAIN rows: {len(train_df)}")
    print(f"TEST rows:  {len(test_df)}")
    print()
    print(f"Missing rate OK:   {missing_rate_ok}")
    print(f"Segment length OK: {segment_length_ok}")
    print(f"Label OK:          {label_ok}")
    print()
    print(f"OVERALL STATUS: {overall_status}")

    if overall_status == "PASS":
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
