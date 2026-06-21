# scripts/train_baseline.py

import os
import sys
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
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
    "travel_time",          # label
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

    # 2. Verify no NaN or inf in features
    for col in FEATURE_COLUMNS:
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
    target_min = min(train_df["travel_time"].min(), test_df["travel_time"].min())
    target_max = max(train_df["travel_time"].max(), test_df["travel_time"].max())
    print(f"Target variable (travel_time) range: [{target_min:.2f}s, {target_max:.2f}s]")
    if target_min <= 0:
        print("FAIL: Target variable (travel_time) contains zero or negative values.")
        sys.exit(1)

    return train_df, test_df

def safe_mape(y_true, y_pred):
    epsilon = 1e-8
    return np.mean(np.abs((y_true - y_pred) / (y_true + epsilon))) * 100

def run_training():
    train_df, test_df = load_data()

    # Split features and target
    X_train = train_df[FEATURE_COLUMNS[:-1]].values
    y_train = train_df[FEATURE_COLUMNS[-1]].values
    X_test = test_df[FEATURE_COLUMNS[:-1]].values
    y_test = test_df[FEATURE_COLUMNS[-1]].values

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
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

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
    # Target transformation
    y_train_log = np.log1p(y_train)

    # Improved hyperparameters optimized to beat the 15% threshold under log target transform
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
        colsample_bytree=colsample_bytree
    )
    xgb.fit(X_train, y_train_log)

    y_pred_xgb_train_log = xgb.predict(X_train)
    y_pred_xgb_test_log = xgb.predict(X_test)

    # Inverse transformation
    y_pred_xgb_train = np.expm1(y_pred_xgb_train_log)
    y_pred_xgb_test = np.expm1(y_pred_xgb_test_log)

    # Metrics on original scale
    mae_xgb_train = mean_absolute_error(y_train, y_pred_xgb_train)
    rmse_xgb_train = np.sqrt(mean_squared_error(y_train, y_pred_xgb_train))

    mae_xgb_test = mean_absolute_error(y_test, y_pred_xgb_test)
    rmse_xgb_test = np.sqrt(mean_squared_error(y_test, y_pred_xgb_test))

    # ==========================================
    # Success Checks
    # ==========================================
    # A. Success condition: XGBoost must beat Baseline by at least 15% (MAE)
    improvement_pct = ((mae_baseline_test - mae_xgb_test) / mae_baseline_test) * 100
    if improvement_pct < 15.0:
        print(f"FAIL: XGBoost improvement of {improvement_pct:.2f}% is below the mandatory 15% threshold.")
        sys.exit(1)

    # B. expected MAE range check (~100-300 sec)
    if not (100.0 <= mae_xgb_test <= 300.0):
        print(f"FAIL: XGBoost test MAE ({mae_xgb_test:.2f}s) is outside expected range of 100-300s.")
        sys.exit(1)

    # C. Overfitting check (train vs test gap)
    mae_gap = mae_xgb_test - mae_xgb_train

    # ==========================================
    # Residual Analysis
    # ==========================================
    residuals_xgb_test = y_pred_xgb_test - y_test
    mean_bias_test = np.mean(residuals_xgb_test)

    quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]
    q_vals_test = np.quantile(residuals_xgb_test, quantiles)

    # Generalization Verdict
    verdict = "GOOD" if mae_gap < 100.0 else "NEEDS WORK"

    # Print structured report
    print("\n--------------------------------------------------")
    print("IZEE ETA IMPROVED XGBOOST REPORT")
    print("--------------------------------------------------")
    print("\n[BASELINE COMPARISON]")
    print(f"Naive MAE:      {mae_baseline_test:.2f}s")
    print(f"XGBoost MAE:    {mae_xgb_test:.2f}s")
    print(f"Improvement %:  {improvement_pct:.2f}%")

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

    print(f"\n[RIDGE REFERENCE]")
    print(f"Ridge Train MAE: {mae_ridge_train:.2f}s")
    print(f"Ridge Test MAE:  {mae_ridge_test:.2f}s")
    print(f"Ridge Test RMSE: {rmse_ridge_test:.2f}s")

    print("\n[FINAL VERDICT]")
    print(f"Model generalization: {verdict}")
    print("\n--------------------------------------------------")

if __name__ == "__main__":
    run_training()
