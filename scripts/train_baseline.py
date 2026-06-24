# scripts/train_baseline.py

import os
import sys
import numpy as np
import pandas as pd
import joblib  # Added for saving the model
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

# Force UTF-8 output on Windows terminals to avoid cp1252 encode errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAIN_CSV = os.path.join(BASE_DIR, "scripts", "feature_data", "train_features.csv")
TEST_CSV = os.path.join(BASE_DIR, "scripts", "feature_data", "test_features.csv")

FEATURE_COLUMNS = [
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
    "segment_progress",  # Added critical ETA feature
    "speed",             # Added critical ETA feature
    "direction",         # Added critical ETA feature
    "remaining_time",    # Updated label column
]

def load_data():
    if not os.path.exists(TRAIN_CSV) or not os.path.exists(TEST_CSV):
        print(f"Error: Feature CSVs not found. Run feature_engineering.py first.")
        sys.exit(1)

    train_df = pd.read_csv(TRAIN_CSV)
    test_df = pd.read_csv(TEST_CSV)

    # 1. Verify feature columns identical and match FEATURE_COLUMNS
    for col in FEATURE_COLUMNS:
        if col not in train_df.columns:
            print(f"FAIL: Missing column '{col}' in TRAIN dataset.")
            sys.exit(1)
        if col not in test_df.columns:
            print(f"FAIL: Missing column '{col}' in TEST dataset.")
            sys.exit(1)

    # Reorder columns to ensure consistency
    train_df = train_df[FEATURE_COLUMNS]
    test_df = test_df[FEATURE_COLUMNS]

    # 2. Verify no NaN or inf in features (with specific exceptions for statistical defaults)
    ALLOW_NAN_COLUMNS = {
        "avg_segment_time",
        "std_travel_time"
    }

    for col in FEATURE_COLUMNS:
        if col not in ALLOW_NAN_COLUMNS:
            if train_df[col].isna().sum() > 0:
                print(f"FAIL: NaN values found in TRAIN column '{col}'.")
                sys.exit(1)
            if test_df[col].isna().sum() > 0:
                print(f"FAIL: NaN values found in TEST column '{col}'.")
                sys.exit(1)

        if np.isinf(train_df[col]).sum() > 0:
            print(f"FAIL: Infinite values found in TRAIN column '{col}'.")
            sys.exit(1)
        if np.isinf(test_df[col]).sum() > 0:
            print(f"FAIL: Infinite values found in TEST column '{col}'.")
            sys.exit(1)

    # 3. Target range sanity check
    target_min = min(train_df["remaining_time"].min(), test_df["remaining_time"].min())
    target_max = max(train_df["remaining_time"].max(), test_df["remaining_time"].max())
    print(f"Target variable (remaining_time) range: [{target_min:.2f}s, {target_max:.2f}s]")
    if target_min <= 0:
        print("FAIL: Target variable (remaining_time) contains zero or negative values.")
        sys.exit(1)

    return train_df, test_df

def safe_mape(y_true, y_pred):
    epsilon = 1e-8
    return np.mean(np.abs((y_true - y_pred) / (y_true + epsilon))) * 100

def run_training():
    train_df, test_df = load_data()

    # ==========================================
    # Check 4 — Route Generalization Distribution
    # ==========================================
    print("\n[ROUTE DISTRIBUTION TEST]")
    print(test_df["route_id_encoded"].value_counts())
    print("-" * 35)

    # Split features and target
    X_train = train_df[FEATURE_COLUMNS[:-1]].values.astype(np.float32)
    y_train = train_df[FEATURE_COLUMNS[-1]].values.astype(np.float32)
    X_test = test_df[FEATURE_COLUMNS[:-1]].values.astype(np.float32)
    y_test = test_df[FEATURE_COLUMNS[-1]].values.astype(np.float32)

    print("\nDataset dimensions:")
    print(f"  Train features shape: {X_train.shape}")
    print(f"  Test features shape:  {X_test.shape}")

    # ==========================================
    # 1. Naive Baseline Model (Mean of y_train)
    # ==========================================
    mean_val = np.mean(y_train)
    y_pred_baseline_train = np.full_like(y_train, mean_val)
    y_pred_baseline_test = np.full_like(y_test, mean_val)

    mae_baseline_train = mean_absolute_error(y_train, y_pred_baseline_train)
    rmse_baseline_train = np.sqrt(mean_squared_error(y_train, y_pred_baseline_train))
    mae_baseline_test = mean_absolute_error(y_test, y_pred_baseline_test)
    rmse_baseline_test = np.sqrt(mean_squared_error(y_test, y_pred_baseline_test))

    # ==========================================
    # 2. Ridge Regression Model (with scaling)
    # ==========================================
    from sklearn.impute import SimpleImputer
    imputer = SimpleImputer(strategy="mean")

    X_train_ridge = imputer.fit_transform(X_train)
    X_test_ridge = imputer.transform(X_test)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_ridge)
    X_test_scaled = scaler.transform(X_test_ridge)

    ridge = Ridge()
    ridge.fit(X_train_scaled, y_train)

    y_pred_ridge_train = ridge.predict(X_train_scaled)
    y_pred_ridge_test = ridge.predict(X_test_scaled)

    mae_ridge_train = mean_absolute_error(y_train, y_pred_ridge_train)
    rmse_ridge_train = np.sqrt(mean_squared_error(y_train, y_pred_ridge_train))
    mae_ridge_test = mean_absolute_error(y_test, y_pred_ridge_test)
    rmse_ridge_test = np.sqrt(mean_squared_error(y_test, y_pred_ridge_test))

    # ==========================================
    # 3. XGBoost Model with Target Log Transformation & Regularization
    # ==========================================
    y_train_log = np.log1p(y_train)

    max_depth = 4
    min_child_weight = 2
    subsample = 0.8
    colsample_bytree = 0.8
    learning_rate = 0.12
    n_estimators = 300
    random_state = 42

    xgb = XGBRegressor(
        random_state=random_state,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        min_child_weight=min_child_weight,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        tree_method="hist",
        max_bin=256,
        n_jobs=4
    )
    xgb.fit(X_train, y_train_log)

    y_pred_xgb_train_log = xgb.predict(X_train)
    y_pred_xgb_test_log = xgb.predict(X_test)

    # Inverse transformation
    y_pred_xgb_train = np.expm1(y_pred_xgb_train_log)
    y_pred_xgb_test = np.expm1(y_pred_xgb_test_log)

    # Print sample validation pairs
    print("\n[SAMPLE PREDICTIONS]")
    for real, pred in zip(y_test[:20], y_pred_xgb_test[:20]):
        print(f"Actual={real:.1f}s | Predicted={pred:.1f}s | Error={pred-real:+.1f}s")

    # Metrics on original scale
    mae_xgb_train = mean_absolute_error(y_train, y_pred_xgb_train)
    rmse_xgb_train = np.sqrt(mean_squared_error(y_train, y_pred_xgb_train))
    mae_xgb_test = mean_absolute_error(y_test, y_pred_xgb_test)
    rmse_xgb_test = np.sqrt(mean_squared_error(y_test, y_pred_xgb_test))
    
    # Calculate R2 scores
    r2_train = r2_score(y_train, y_pred_xgb_train)
    r2_test = r2_score(y_test, y_pred_xgb_test)

    # ==========================================
    # Success Checks
    # ==========================================
    improvement_pct = ((mae_baseline_test - mae_xgb_test) / mae_baseline_test) * 100
    if improvement_pct < 15.0:
        print(f"FAIL: XGBoost improvement of {improvement_pct:.2f}% is below the mandatory 15% threshold.")
        sys.exit(1)

    if mae_xgb_test <= 0:
        print("FAIL: Invalid MAE")
        sys.exit(1)

    mae_gap = mae_xgb_test - mae_xgb_train

    # ==========================================
    # Residual Analysis
    # ==========================================
    residuals_xgb_test = y_pred_xgb_test - y_test
    mean_bias_test = np.mean(residuals_xgb_test)

    quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]
    q_vals_test = np.quantile(residuals_xgb_test, quantiles)

    verdict = "GOOD" if mae_gap < 100.0 else "NEEDS WORK"

    # ==========================================
    # Save Model Artifacts
    # ==========================================
    # Check 5 Note: For full real-time inference production deployment later,
    # we must bundle: segment encoder, route encoder, feature order, and standard scaler.
    model_output_path = os.path.join(BASE_DIR, "scripts", "eta_xgb_model.pkl")
    joblib.dump(xgb, model_output_path)
    print(f"Successfully saved trained model artifact to: {model_output_path}")

    # ==========================================
    # PRE-COMMIT INFERENCE TESTING
    # ==========================================
    print("\n[PRE-COMMIT VALIDATION TESTS]")
    try:
        single_row_mock = X_test[0:1]
        mock_pred_log = xgb.predict(single_row_mock)
        mock_pred_seconds = np.expm1(mock_pred_log)[0]
        print(f"  ✅ PASS: Single-row real-time streaming smoke inference test.")
        print(f"           Sample Prediction Output: {mock_pred_seconds:.2f}s")
    except Exception as e:
        print(f"  ❌ FAIL: Single-row tracking inference crashed: {str(e)}")
        sys.exit(1)

    # Print structured report
    print("\n--------------------------------------------------")
    print("IZEE ETA IMPROVED XGBOOST REPORT")
    print("--------------------------------------------------")
    print("\n[BASELINE COMPARISON]")
    print(f"Naive MAE:      {mae_baseline_test:.2f}s")
    print(f"XGBoost MAE:    {mae_xgb_test:.2f}s")
    print(f"Improvement %:  {improvement_pct:.2f}%")

    print("\n[ACCURACY & QUALITY METRICS]")
    print(f"Train R² Score: {r2_train:.4f}")
    print(f"Test R² Score:  {r2_test:.4f}")

    print("\n[OVERFITTING CHECK]")
    print(f"Train MAE:      {mae_xgb_train:.2f}s")
    print(f"Test MAE:       {mae_xgb_test:.2f}s")
    print(f"Gap:            {mae_gap:.2f}s")

    print("\n[MODEL CONFIG]")
    print(f"max_depth:        {max_depth}")
    print(f"min_child_weight: {min_child_weight}")
    print(f"subsample:        {subsample}")
    print(f"colsample_bytree: {colsample_bytree}")
    print(f"learning_rate:    {learning_rate}")
    print(f"n_estimators:     {n_estimators}")

    print("\n[RESIDUAL ANALYSIS]")
    print(f"Mean error:     {mean_bias_test:.4f}s")
    print("Quantiles:")
    for q, val in zip(quantiles, q_vals_test):
        print(f"   {q * 100:>3.0f}%: {val:>+7.2f}s")

    # ==========================================
    # Check 3 — Error by ETA range
    # ==========================================
    print("\n[ERROR BY ETA RANGE]")
    bins = [
        (0, 300),
        (300, 900),
        (900, 99999)
    ]
    for low, high in bins:
        mask = (y_test >= low) & (y_test < high)
        if mask.sum() > 0:
            bin_mae = mean_absolute_error(y_test[mask], y_pred_xgb_test[mask])
            print(f"  {low:5d} to {high:5d}s -> Count: {mask.sum():<7d} | MAE: {bin_mae:.2f}s")
        else:
            print(f"  {low:5d} to {high:5d}s -> Count: 0       | MAE: N/A")

    # ==========================================
    # Optional Check 1 — ETA Accuracy Bands
    # ==========================================
    abs_error = np.abs(y_pred_xgb_test - y_test)
    print("\n[ETA ACCURACY BANDS]")
    for threshold in [30, 60, 120, 300]:
        pct = np.mean(abs_error <= threshold) * 100
        print(f"  Within {threshold:3d}s: {pct:.2f}%")

    # ==========================================
    # Optional Check 2 — Error by Route Performance
    # ==========================================
    print("\n[ERROR BY ROUTE]")
    tmp = test_df.copy()
    tmp["error"] = np.abs(y_pred_xgb_test - y_test)
    for route, group in tmp.groupby("route_id_encoded"):
        print(f"  Route {int(route)}: count={len(group):<6d} | MAE={group['error'].mean():.2f}s")

    print(f"\n[RIDGE REFERENCE]")
    print(f"Ridge Train MAE: {mae_ridge_train:.2f}s")
    print(f"Ridge Test MAE:  {mae_ridge_test:.2f}s")
    print(f"Ridge Test RMSE: {rmse_ridge_test:.2f}s")

    print("\n[FINAL VERDICT]")
    print(f"Model generalization: {verdict}")
    print("\n--------------------------------------------------")
    
    print("\n[FEATURE IMPORTANCE]")
    importance_sum = np.sum(xgb.feature_importances_)
    print(f"Total Importance Sum: {importance_sum:.4f} (Expected: 1.0000)")
    print("-" * 35)
    for name, score in zip(FEATURE_COLUMNS[:-1], xgb.feature_importances_):
        flag = " ⚠️ [CRITICAL HIGH DEPENDENCY]" if score > 0.70 and "encoded" in name else ""
        print(f"{name:25s}: {score:.4f}{flag}")

if __name__ == "__main__":
    run_training()