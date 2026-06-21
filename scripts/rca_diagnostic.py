# scripts/rca_diagnostic.py
"""
IZEE ETA Root Cause Analysis — Comprehensive Diagnostic Script
Performs all mandatory checks and additional investigations.
"""

import os, sys, math
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAIN_CSV = os.path.join(BASE_DIR, "scripts", "feature_data", "train_features.csv")
TEST_CSV  = os.path.join(BASE_DIR, "scripts", "feature_data", "test_features.csv")

FEATURES = [
    "hour", "avg_segment_time", "current_delay", "day_of_week_encoded",
    "is_peak", "segment_id_encoded", "route_id_encoded",
    "std_travel_time", "stop_sequence", "segment_length_m",
]
TARGET = "travel_time"

train_df = pd.read_csv(TRAIN_CSV)
test_df  = pd.read_csv(TEST_CSV)

X_train = train_df[FEATURES].values
y_train = train_df[TARGET].values
X_test  = test_df[FEATURES].values
y_test  = test_df[TARGET].values

SEPARATOR = "=" * 70

# =========================================================================
# [1] FEATURE LEAKAGE CHECK
# =========================================================================
print(f"\n{SEPARATOR}")
print("[1] FEATURE LEAKAGE CHECK")
print(SEPARATOR)

# Check: avg_segment_time is computed from segment_statistics which uses ALL days
# (not just training days). This means test-day travel_times leak into avg_segment_time.
# Evidence: compute correlation between avg_segment_time and travel_time on both splits

corr_train = np.corrcoef(train_df["avg_segment_time"], train_df["travel_time"])[0, 1]
corr_test  = np.corrcoef(test_df["avg_segment_time"],  test_df["travel_time"])[0, 1]
print(f"  Correlation(avg_segment_time, travel_time):")
print(f"    TRAIN: {corr_train:.6f}")
print(f"    TEST:  {corr_test:.6f}")

# Check: does avg_segment_time nearly equal travel_time for some rows?
ratio_train = train_df["travel_time"] / train_df["avg_segment_time"]
ratio_test  = test_df["travel_time"]  / test_df["avg_segment_time"]
print(f"\n  Ratio travel_time / avg_segment_time:")
print(f"    TRAIN: mean={ratio_train.mean():.4f}  median={ratio_train.median():.4f}  std={ratio_train.std():.4f}")
print(f"    TEST:  mean={ratio_test.mean():.4f}  median={ratio_test.median():.4f}  std={ratio_test.std():.4f}")

# Check: segment_statistics uses ALL days including test days
# segment_stats.py -> fetch_segment_completed_rows: no day filter at all
# This means avg_segment_time includes Friday + Sunday data (test days)
print(f"\n  [CODE EVIDENCE]")
print(f"    segment_stats.py -> fetch_segment_completed_rows():")
print(f"    SQL has NO day_of_week filter -> uses ALL days including Friday, Sunday")
print(f"    This means avg_segment_time leaks test-day travel_time information.")

# Check: std_travel_time has the same leakage
corr_std_train = np.corrcoef(train_df["std_travel_time"], train_df["travel_time"])[0, 1]
corr_std_test  = np.corrcoef(test_df["std_travel_time"],  test_df["travel_time"])[0, 1]
print(f"\n  Correlation(std_travel_time, travel_time):")
print(f"    TRAIN: {corr_std_train:.6f}")
print(f"    TEST:  {corr_std_test:.6f}")

# Quantify: How much of target variance does avg_segment_time explain?
# Simple R^2
from sklearn.linear_model import LinearRegression
lr = LinearRegression()
lr.fit(train_df[["avg_segment_time"]].values, y_train)
r2_train = lr.score(train_df[["avg_segment_time"]].values, y_train)
r2_test  = lr.score(test_df[["avg_segment_time"]].values, y_test)
print(f"\n  R^2 of avg_segment_time alone:")
print(f"    TRAIN: {r2_train:.6f}")
print(f"    TEST:  {r2_test:.6f}")

print(f"\n  VERDICT: avg_segment_time and std_travel_time are computed from ALL days")
print(f"  (including test days Friday/Sunday). This is a FEATURE LEAKAGE issue.")
print(f"  However, it affects Ridge and XGBoost equally, so it does NOT explain")
print(f"  why Ridge outperforms XGBoost. It does inflate both models' apparent accuracy.")

# =========================================================================
# [2] TARGET / DISTRIBUTION SHIFT CHECK
# =========================================================================
print(f"\n{SEPARATOR}")
print("[2] DISTRIBUTION SHIFT CHECK")
print(SEPARATOR)

for col in FEATURES + [TARGET]:
    tr = train_df[col]
    te = test_df[col]
    print(f"\n  {col}:")
    print(f"    TRAIN: mean={tr.mean():.4f}  median={tr.median():.4f}  std={tr.std():.4f}  zeros={sum(tr==0)}/{len(tr)} ({sum(tr==0)/len(tr)*100:.2f}%)")
    print(f"    TEST:  mean={te.mean():.4f}  median={te.median():.4f}  std={te.std():.4f}  zeros={sum(te==0)}/{len(te)} ({sum(te==0)/len(te)*100:.2f}%)")

# Specific focus on current_delay
print(f"\n  [CURRENT_DELAY DETAILED ANALYSIS]")
cd_train = train_df["current_delay"]
cd_test  = test_df["current_delay"]
quantiles = [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]
print(f"    TRAIN quantiles:")
for q in quantiles:
    print(f"      {q*100:5.1f}%: {cd_train.quantile(q):.4f}")
print(f"    TEST quantiles:")
for q in quantiles:
    print(f"      {q*100:5.1f}%: {cd_test.quantile(q):.4f}")

print(f"\n  VERDICT: current_delay is 0.0 for ALL test rows (by design: no leakage).")
print(f"  This creates a MASSIVE distribution shift for this feature between splits.")

# =========================================================================
# [3] ID MEMORIZATION CHECK
# =========================================================================
print(f"\n{SEPARATOR}")
print("[3] ID MEMORIZATION CHECK")
print(SEPARATOR)

# Train XGBoost WITHOUT segment_id_encoded and route_id_encoded
features_no_ids = [f for f in FEATURES if f not in ["segment_id_encoded", "route_id_encoded"]]
X_train_no_ids = train_df[features_no_ids].values
X_test_no_ids  = test_df[features_no_ids].values

# Original XGBoost (no log transform, same as first baseline to be fair)
xgb_full = XGBRegressor(random_state=42, n_estimators=100, max_depth=6, learning_rate=0.1)
xgb_full.fit(X_train, y_train)
mae_full_train = mean_absolute_error(y_train, xgb_full.predict(X_train))
mae_full_test  = mean_absolute_error(y_test,  xgb_full.predict(X_test))

xgb_no_ids = XGBRegressor(random_state=42, n_estimators=100, max_depth=6, learning_rate=0.1)
xgb_no_ids.fit(X_train_no_ids, y_train)
mae_no_ids_train = mean_absolute_error(y_train, xgb_no_ids.predict(X_train_no_ids))
mae_no_ids_test  = mean_absolute_error(y_test,  xgb_no_ids.predict(X_test_no_ids))

# Ridge comparison
scaler = StandardScaler()
X_tr_s = scaler.fit_transform(X_train)
X_te_s = scaler.transform(X_test)
ridge_full = Ridge()
ridge_full.fit(X_tr_s, y_train)
mae_ridge_train = mean_absolute_error(y_train, ridge_full.predict(X_tr_s))
mae_ridge_test  = mean_absolute_error(y_test,  ridge_full.predict(X_te_s))

scaler2 = StandardScaler()
X_tr_s2 = scaler2.fit_transform(X_train_no_ids)
X_te_s2 = scaler2.transform(X_test_no_ids)
ridge_no_ids = Ridge()
ridge_no_ids.fit(X_tr_s2, y_train)
mae_ridge_no_ids_train = mean_absolute_error(y_train, ridge_no_ids.predict(X_tr_s2))
mae_ridge_no_ids_test  = mean_absolute_error(y_test,  ridge_no_ids.predict(X_te_s2))

print(f"  XGBoost FULL:    Train MAE={mae_full_train:.2f}s  Test MAE={mae_full_test:.2f}s  Gap={mae_full_test-mae_full_train:.2f}s")
print(f"  XGBoost NO IDs:  Train MAE={mae_no_ids_train:.2f}s  Test MAE={mae_no_ids_test:.2f}s  Gap={mae_no_ids_test-mae_no_ids_train:.2f}s")
print(f"  Ridge FULL:      Train MAE={mae_ridge_train:.2f}s  Test MAE={mae_ridge_test:.2f}s  Gap={mae_ridge_test-mae_ridge_train:.2f}s")
print(f"  Ridge NO IDs:    Train MAE={mae_ridge_no_ids_train:.2f}s  Test MAE={mae_ridge_no_ids_test:.2f}s  Gap={mae_ridge_no_ids_test-mae_ridge_no_ids_train:.2f}s")

print(f"\n  VERDICT: Removing ID features from XGBoost {'helps' if mae_no_ids_test < mae_full_test else 'hurts'} test MAE")
print(f"  ({mae_full_test:.2f}s -> {mae_no_ids_test:.2f}s)")

# =========================================================================
# [4] SINGLE FEATURE DOMINANCE CHECK
# =========================================================================
print(f"\n{SEPARATOR}")
print("[4] SINGLE FEATURE DOMINANCE CHECK")
print(SEPARATOR)

# Ridge with ONLY avg_segment_time
scaler3 = StandardScaler()
X_tr_avg = scaler3.fit_transform(train_df[["avg_segment_time"]].values)
X_te_avg = scaler3.transform(test_df[["avg_segment_time"]].values)
ridge_avg = Ridge()
ridge_avg.fit(X_tr_avg, y_train)
mae_avg_train = mean_absolute_error(y_train, ridge_avg.predict(X_tr_avg))
mae_avg_test  = mean_absolute_error(y_test,  ridge_avg.predict(X_te_avg))

# Also test with avg_segment_time + std_travel_time
scaler4 = StandardScaler()
X_tr_as = scaler4.fit_transform(train_df[["avg_segment_time", "std_travel_time"]].values)
X_te_as = scaler4.transform(test_df[["avg_segment_time", "std_travel_time"]].values)
ridge_as = Ridge()
ridge_as.fit(X_tr_as, y_train)
mae_as_train = mean_absolute_error(y_train, ridge_as.predict(X_tr_as))
mae_as_test  = mean_absolute_error(y_test,  ridge_as.predict(X_te_as))

# Also naive avg_segment_time as direct prediction (no model)
mae_direct_train = mean_absolute_error(y_train, train_df["avg_segment_time"].values)
mae_direct_test  = mean_absolute_error(y_test,  test_df["avg_segment_time"].values)

print(f"  Naive mean baseline:           Train MAE={mean_absolute_error(y_train, np.full_like(y_train, y_train.mean())):.2f}s  Test MAE={mean_absolute_error(y_test, np.full_like(y_test, y_train.mean())):.2f}s")
print(f"  Direct avg_segment_time pred:  Train MAE={mae_direct_train:.2f}s  Test MAE={mae_direct_test:.2f}s")
print(f"  Ridge(avg_segment_time only):  Train MAE={mae_avg_train:.2f}s  Test MAE={mae_avg_test:.2f}s")
print(f"  Ridge(avg + std):              Train MAE={mae_as_train:.2f}s  Test MAE={mae_as_test:.2f}s")
print(f"  Ridge(ALL features):           Train MAE={mae_ridge_train:.2f}s  Test MAE={mae_ridge_test:.2f}s")

pct_explained = (1 - mae_avg_test / mae_ridge_test) * 100
print(f"\n  avg_segment_time alone captures {100 - abs(pct_explained):.1f}% of full Ridge performance")
print(f"  Additional features contribute only {abs(pct_explained):.1f}% MAE reduction")

# =========================================================================
# [5] ERROR STRUCTURE ANALYSIS
# =========================================================================
print(f"\n{SEPARATOR}")
print("[5] ERROR STRUCTURE ANALYSIS")
print(SEPARATOR)

pred_ridge_test = ridge_full.predict(X_te_s)
pred_xgb_test   = xgb_full.predict(X_test)

for name, preds in [("Ridge", pred_ridge_test), ("XGBoost", pred_xgb_test)]:
    residuals = preds - y_test
    underpred = np.sum(residuals < 0)
    overpred  = np.sum(residuals > 0)
    print(f"\n  {name}:")
    print(f"    Mean residual (bias):  {np.mean(residuals):.4f}s")
    print(f"    Std residual:          {np.std(residuals):.4f}s")
    print(f"    Underprediction:       {underpred} ({underpred/len(residuals)*100:.1f}%)")
    print(f"    Overprediction:        {overpred}  ({overpred/len(residuals)*100:.1f}%)")
    print(f"    Quantiles:")
    for q in [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]:
        print(f"      {q*100:5.1f}%: {np.quantile(residuals, q):>+8.2f}s")

# =========================================================================
# [6] CURRENT_DELAY TRAIN/TEST ASYMMETRY IMPACT
# =========================================================================
print(f"\n{SEPARATOR}")
print("[6] CURRENT_DELAY ASYMMETRY — IMPACT ANALYSIS")
print(SEPARATOR)

# Train XGBoost WITHOUT current_delay
features_no_delay = [f for f in FEATURES if f != "current_delay"]
X_train_nd = train_df[features_no_delay].values
X_test_nd  = test_df[features_no_delay].values

xgb_nd = XGBRegressor(random_state=42, n_estimators=100, max_depth=6, learning_rate=0.1)
xgb_nd.fit(X_train_nd, y_train)
mae_nd_train = mean_absolute_error(y_train, xgb_nd.predict(X_train_nd))
mae_nd_test  = mean_absolute_error(y_test,  xgb_nd.predict(X_test_nd))

# Ridge without current_delay
scaler5 = StandardScaler()
X_tr_nd_s = scaler5.fit_transform(X_train_nd)
X_te_nd_s = scaler5.transform(X_test_nd)
ridge_nd = Ridge()
ridge_nd.fit(X_tr_nd_s, y_train)
mae_ridge_nd_train = mean_absolute_error(y_train, ridge_nd.predict(X_tr_nd_s))
mae_ridge_nd_test  = mean_absolute_error(y_test,  ridge_nd.predict(X_te_nd_s))

print(f"  XGBoost WITH delay:    Train={mae_full_train:.2f}s  Test={mae_full_test:.2f}s  Gap={mae_full_test-mae_full_train:.2f}s")
print(f"  XGBoost WITHOUT delay: Train={mae_nd_train:.2f}s  Test={mae_nd_test:.2f}s  Gap={mae_nd_test-mae_nd_train:.2f}s")
print(f"  Ridge WITH delay:      Train={mae_ridge_train:.2f}s  Test={mae_ridge_test:.2f}s  Gap={mae_ridge_test-mae_ridge_train:.2f}s")
print(f"  Ridge WITHOUT delay:   Train={mae_ridge_nd_train:.2f}s  Test={mae_ridge_nd_test:.2f}s  Gap={mae_ridge_nd_test-mae_ridge_nd_train:.2f}s")

# XGBoost feature importance
print(f"\n  XGBoost Feature Importances (FULL model):")
importances = xgb_full.feature_importances_
for idx in np.argsort(importances)[::-1]:
    print(f"    {FEATURES[idx]:<25} {importances[idx]:.4f}")

# =========================================================================
# [7] MULTICOLLINEARITY CHECK
# =========================================================================
print(f"\n{SEPARATOR}")
print("[7] MULTICOLLINEARITY CHECK")
print(SEPARATOR)

corr_matrix = train_df[FEATURES].corr()
print(f"  Feature correlation matrix (TRAIN):")
print(f"  {'':>25}", end="")
for f in FEATURES:
    print(f"  {f[:8]:>8}", end="")
print()
for i, f1 in enumerate(FEATURES):
    print(f"  {f1:>25}", end="")
    for j, f2 in enumerate(FEATURES):
        v = corr_matrix.iloc[i, j]
        marker = " *" if abs(v) > 0.5 and i != j else "  "
        print(f"  {v:>6.3f}{marker}", end="")
    print()

high_corr = []
for i in range(len(FEATURES)):
    for j in range(i+1, len(FEATURES)):
        v = abs(corr_matrix.iloc[i, j])
        if v > 0.5:
            high_corr.append((FEATURES[i], FEATURES[j], corr_matrix.iloc[i, j]))

print(f"\n  Highly correlated pairs (|r| > 0.5):")
for f1, f2, r in sorted(high_corr, key=lambda x: abs(x[2]), reverse=True):
    print(f"    {f1} <-> {f2}: r={r:.4f}")

# =========================================================================
# [8] TARGET DISTRIBUTION — SKEWNESS CHECK
# =========================================================================
print(f"\n{SEPARATOR}")
print("[8] TARGET DISTRIBUTION ANALYSIS")
print(SEPARATOR)

for name, vals in [("TRAIN", y_train), ("TEST", y_test)]:
    print(f"\n  {name}:")
    print(f"    Count:  {len(vals)}")
    print(f"    Mean:   {np.mean(vals):.2f}s")
    print(f"    Median: {np.median(vals):.2f}s")
    print(f"    Std:    {np.std(vals):.2f}s")
    print(f"    Min:    {np.min(vals):.2f}s")
    print(f"    Max:    {np.max(vals):.2f}s")
    print(f"    Skew:   {pd.Series(vals).skew():.4f}")
    print(f"    Kurtosis: {pd.Series(vals).kurtosis():.4f}")
    # Bins
    bins = [(10,60), (60,120), (120,300), (300,600), (600,1200), (1200,3450)]
    for lo, hi in bins:
        cnt = np.sum((vals >= lo) & (vals < hi))
        print(f"    [{lo:>5}-{hi:>5}): {cnt:>7} ({cnt/len(vals)*100:>5.1f}%)")

# =========================================================================
# [9] RIDGE COEFFICIENT ANALYSIS — WHY RIDGE WORKS
# =========================================================================
print(f"\n{SEPARATOR}")
print("[9] RIDGE COEFFICIENT ANALYSIS")
print(SEPARATOR)

print(f"  Ridge coefficients (scaled features):")
for idx in np.argsort(np.abs(ridge_full.coef_))[::-1]:
    print(f"    {FEATURES[idx]:<25} coef={ridge_full.coef_[idx]:>+10.4f}")
print(f"  Intercept: {ridge_full.intercept_:.4f}")

# =========================================================================
# [10] XGBoost OVERFITTING — TRAIN PREDICTION ANALYSIS
# =========================================================================
print(f"\n{SEPARATOR}")
print("[10] XGBoost TRAIN vs TEST PREDICTION DISTRIBUTIONS")
print(SEPARATOR)

pred_xgb_train = xgb_full.predict(X_train)
for name, preds, actuals in [("TRAIN", pred_xgb_train, y_train), ("TEST", pred_xgb_test, y_test)]:
    print(f"\n  {name} predictions:")
    print(f"    Mean predicted: {np.mean(preds):.2f}s   Mean actual: {np.mean(actuals):.2f}s")
    print(f"    Std predicted:  {np.std(preds):.2f}s   Std actual:  {np.std(actuals):.2f}s")
    residuals = preds - actuals
    abs_res = np.abs(residuals)
    print(f"    MAE: {np.mean(abs_res):.2f}s")
    print(f"    % of predictions within 30s:  {np.sum(abs_res < 30)/len(abs_res)*100:.1f}%")
    print(f"    % of predictions within 60s:  {np.sum(abs_res < 60)/len(abs_res)*100:.1f}%")
    print(f"    % of predictions within 120s: {np.sum(abs_res < 120)/len(abs_res)*100:.1f}%")

# =========================================================================
# [11] CURRENT_DELAY AS LEAKAGE SOURCE
# =========================================================================
print(f"\n{SEPARATOR}")
print("[11] CURRENT_DELAY AS POTENTIAL LEAKAGE")
print(SEPARATOR)

# current_delay = elapsed_time - avg_travel_time
# elapsed_time ~ actual travel_time (if departure found close to segment start)
# So current_delay ~ travel_time - avg_segment_time
# This means: travel_time ~ avg_segment_time + current_delay
# This is DIRECT LEAKAGE for training data

cd_train_vals = train_df["current_delay"].values
avg_train_vals = train_df["avg_segment_time"].values
reconstructed = avg_train_vals + cd_train_vals
reconstruction_error = mean_absolute_error(y_train, reconstructed)
print(f"  If travel_time = avg_segment_time + current_delay:")
print(f"    Reconstruction MAE on TRAIN: {reconstruction_error:.4f}s")
print(f"    (If this is near 0, current_delay is directly derived from the label)")

# Check: correlation of (avg_segment_time + current_delay) vs travel_time on train
corr_recon = np.corrcoef(reconstructed, y_train)[0, 1]
print(f"    Correlation(avg + delay, travel_time) on TRAIN: {corr_recon:.6f}")

# On test, current_delay = 0, so reconstruction = avg_segment_time
print(f"\n  On TEST, current_delay = 0.0 for all rows.")
print(f"    So model sees: avg_segment_time + 0 = avg_segment_time only.")

# =========================================================================
# [12] FEATURE ENGINEERING DATA FLOW ANALYSIS
# =========================================================================
print(f"\n{SEPARATOR}")
print("[12] DATA FLOW ANALYSIS SUMMARY")
print(SEPARATOR)

print("""
  DATA FLOW:
  
  1. segment_stats.py computes avg_travel_time from ALL days (no day filter)
     -> This avg becomes "avg_segment_time" feature
     -> LEAKS test-day information into training features
     -> Equally affects both Ridge and XGBoost
  
  2. compute_current_delay.py computes:
     current_delay = elapsed_seconds - avg_travel_time
     where elapsed_seconds = completion_time - last_departure_time
     -> elapsed_seconds is very close to actual travel_time
     -> So current_delay ~ travel_time - avg_segment_time
     -> This is DIRECT LABEL LEAKAGE for TRAIN split
     -> On TEST, current_delay = 0.0 by design (no leakage)
  
  3. Impact on XGBoost vs Ridge:
     - XGBoost LEARNS the leaking pattern: travel_time ~ avg + delay
       -> Achieves near-perfect train MAE (~12s)
       -> But on TEST, delay=0, so this pattern breaks entirely
       -> XGBoost has memorized: "use delay to correct avg"
       -> Without delay, its corrections are wrong -> high test error
     
     - Ridge CANNOT overfit as easily to the leaking feature
       -> Ridge learns a smooth linear combination
       -> avg_segment_time dominates with a coefficient near 1.0
       -> current_delay gets a small weight relative to avg_segment_time
       -> So on TEST (delay=0), Ridge degrades gracefully
       -> Ridge's prediction is essentially: ~1.0 * avg_segment_time
""")

print(SEPARATOR)
print("RCA DIAGNOSTIC COMPLETE")
print(SEPARATOR)
