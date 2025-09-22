# Water Usage Calculation Logic

## Overview

The `insert_actual_runs` method in `universal_database_manager.py` now includes comprehensive usage calculation logic that matches the previous SQLite implementation. This document explains the calculations used for different usage_flag situations.

## Environment Variable Configuration

The water usage variance thresholds are now configurable via environment variables:

- **`HIGH_WATER_USAGE`**: Multiplier for determining "too high" usage (default: 2.0)
- **`LOW_WATER_USAGE`**: Multiplier for determining "too low" usage (default: 0.5)

### Examples:
```bash
# Set custom thresholds
export HIGH_WATER_USAGE=2.5  # Flag as too high when > 2.5x expected
export LOW_WATER_USAGE=0.3   # Flag as too low when < 0.3x expected

# Use defaults (no environment variables needed)
# HIGH_WATER_USAGE defaults to 2.0
# LOW_WATER_USAGE defaults to 0.5
```

The system validates these values:
- Must be positive numbers
- HIGH_WATER_USAGE must be greater than LOW_WATER_USAGE
- Invalid values fall back to defaults with warning logs

## Zone Flow Rate Data

Flow rates are stored in the `zones` table with the `average_flow_rate` column (in GPM - Gallons Per Minute).

Example zone flow rates from `config/zones.json`:
- Zone 1 (Front Right Turf): 2.5 GPM
- Zone 4 (Front Planters & Pots): 1.0 GPM  
- Zone 8 (Rear Left Beds at Fence): 11.3 GPM
- Zone 10 (Rear Left Pots, Baskets & Planters): 3.9 GPM

## Usage Flag Calculations

### 1. `zero_reported` Usage Flag

**When Applied:**
- `actual_gallons` is 0 or NULL
- This was the main issue - the system now estimates usage when scraped data shows 0 gallons

**Calculation:**
```
expected_gallons = zone_average_flow_rate * duration_minutes
usage_value = expected_gallons
usage_type = 'estimated'
usage_flag = 'zero_reported'
```

**Example:**
- Zone 8 (11.3 GPM) runs for 3 minutes, actual_gallons = 0
- Expected: 11.3 GPM × 3 min = 33.9 gallons
- Result: usage = 33.9, usage_type = 'estimated', usage_flag = 'zero_reported'

### 2. `too_high` Usage Flag

**When Applied:**
- `actual_gallons` > configured HIGH_WATER_USAGE threshold × expected_gallons
- Configurable via environment variable: `HIGH_WATER_USAGE` (default: 2.0)

**Calculation:**
```
expected_gallons = zone_average_flow_rate * duration_minutes
usage_ratio = actual_gallons / expected_gallons
high_threshold = get_water_usage_thresholds()[0]  # From HIGH_WATER_USAGE env var
if usage_ratio > high_threshold:
    usage_flag = 'too_high'
    usage_type = 'actual'
    usage_value = actual_gallons
```

**Example:**
- Zone 1 (2.5 GPM) runs for 4 minutes, actual_gallons = 25.0
- Expected: 2.5 GPM × 4 min = 10.0 gallons
- Ratio: 25.0 ÷ 10.0 = 2.5
- Since 2.5 > 2.0 (default threshold): usage_flag = 'too_high'

### 3. `too_low` Usage Flag

**When Applied:**
- `actual_gallons` < configured LOW_WATER_USAGE threshold × expected_gallons
- Configurable via environment variable: `LOW_WATER_USAGE` (default: 0.5)

**Calculation:**
```
expected_gallons = zone_average_flow_rate * duration_minutes
usage_ratio = actual_gallons / expected_gallons
low_threshold = get_water_usage_thresholds()[1]  # From LOW_WATER_USAGE env var
if usage_ratio < low_threshold:
    usage_flag = 'too_low'
    usage_type = 'actual'
    usage_value = actual_gallons
```

**Example:**
- Zone 10 (3.9 GPM) runs for 5 minutes, actual_gallons = 8.0
- Expected: 3.9 GPM × 5 min = 19.5 gallons
- Ratio: 8.0 ÷ 19.5 = 0.41
- Since 0.41 < 0.5 (default threshold): usage_flag = 'too_low'

### 4. `normal` Usage Flag

**When Applied:**
- LOW_WATER_USAGE × expected_gallons ≤ `actual_gallons` ≤ HIGH_WATER_USAGE × expected_gallons
- Within the configured threshold range (default: 0.5x to 2.0x expected)
- OR no flow rate data available for comparison

**Calculation:**
```
expected_gallons = zone_average_flow_rate * duration_minutes
usage_ratio = actual_gallons / expected_gallons
if 0.5 <= usage_ratio <= 2.0:
    usage_flag = 'normal'
    usage_type = 'actual'
    usage_value = actual_gallons
```

**Example:**
- Zone 4 (1.0 GPM) runs for 6 minutes, actual_gallons = 7.2
- Expected: 1.0 GPM × 6 min = 6.0 gallons
- Ratio: 7.2 ÷ 6.0 = 1.2
- Since 0.5 ≤ 1.2 ≤ 2.0: usage_flag = 'normal'

## Implementation Details

### Database Schema Support

Both SQLite and PostgreSQL schemas include:
- `usage_type`: 'actual' or 'estimated'
- `usage`: Contains either actual_gallons or estimated value
- `usage_flag`: 'normal', 'too_high', 'too_low', or 'zero_reported'
- `actual_gallons`: Original scraped value (preserved)

### Thresholds

The current thresholds match the SQLite `WaterUsageEstimator` defaults:
- **High Usage Threshold**: Configurable via `HIGH_WATER_USAGE` environment variable (default: 2.0x = 200% of expected)
- **Low Usage Threshold**: Configurable via `LOW_WATER_USAGE` environment variable (default: 0.5x = 50% of expected)

### Logging

The system logs detailed information for debugging:
- Estimated calculations when actual_gallons = 0
- Too high/too low determinations with ratios
- Normal usage confirmations
- Missing flow rate warnings

## Usage Examples by Zone

### Zone 1 (Front Right Turf - 2.5 GPM)
- 4 min run, 0 gallons → usage = 10.0g, flag = 'zero_reported'
- 4 min run, 8.5 gallons → usage = 8.5g, flag = 'normal' (ratio = 0.85)
- 4 min run, 22.0 gallons → usage = 22.0g, flag = 'too_high' (ratio = 2.2)
- 4 min run, 3.5 gallons → usage = 3.5g, flag = 'too_low' (ratio = 0.35)

### Zone 8 (Rear Left Beds - 11.3 GPM)
- 3 min run, 0 gallons → usage = 33.9g, flag = 'zero_reported'
- 3 min run, 25.0 gallons → usage = 25.0g, flag = 'normal' (ratio = 0.74)
- 3 min run, 75.0 gallons → usage = 75.0g, flag = 'too_high' (ratio = 2.21)
- 3 min run, 12.0 gallons → usage = 12.0g, flag = 'too_low' (ratio = 0.35)

## Benefits

1. **Accurate Water Usage Tracking**: No more missing data when flow meters report 0
2. **Anomaly Detection**: Automatic flagging of unusually high/low usage
3. **Maintenance Alerts**: Too high/too low flags help identify system issues
4. **Cost Analysis**: Proper usage values enable accurate water cost calculations
5. **Historical Consistency**: Same logic as previous SQLite implementation
