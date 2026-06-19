# Delay detection thresholds (multiplier of avg_travel_time)
DELAY_THRESHOLD_LOW = 1.5
DELAY_THRESHOLD_MEDIUM = 2.0
DELAY_THRESHOLD_HIGH = 3.0

# Dwell time thresholds (seconds)
DWELL_THRESHOLD_MEDIUM = 120
DWELL_THRESHOLD_HIGH = 300

# Disruption detection (number of delayed vehicles on same route)
DISRUPTION_THRESHOLD_MEDIUM = 3
DISRUPTION_THRESHOLD_HIGH = 5

# Alert expiry durations (minutes)
ALERT_EXPIRY_DELAY = 10
ALERT_EXPIRY_DWELL = 15
ALERT_EXPIRY_DISRUPTION = 20

# Same entity + same alert type inside this window is skipped.
DEDUP_WINDOW_MINUTES = 10
