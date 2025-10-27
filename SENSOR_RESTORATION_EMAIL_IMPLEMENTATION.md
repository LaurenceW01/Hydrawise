# Sensor Restoration Email Implementation

## Version: v4.3.12
## Date: October 27, 2025

## Overview

Implemented one-time email notification when the rain sensor stops blocking irrigation (restoration notification). This complements the existing ongoing critical alerts sent while the sensor is actively blocking irrigation.

## Problem Statement

Previously, the system would:
- ✅ Send email alerts EVERY time the sensor was actively stopping irrigation (correct behavior)
- ❌ NOT send any email when sensor status changed from stopping → not stopping (missing feature)

Users needed to know when irrigation was restored and automatic watering resumed.

## Solution Implemented

### Email Behavior Matrix

| Sensor Status | Change? | Email Action |
|---------------|---------|--------------|
| IS stopping irrigation | No (ongoing) | ✅ Send email EVERY collection run (critical alert) |
| IS stopping irrigation | Yes (just activated) | ✅ Send email once (activation alert) |
| NOT stopping irrigation | No (ongoing) | ❌ No email |
| NOT stopping irrigation | Yes (just deactivated) | ✅ Send email ONCE (restoration alert) |

### Key Features

1. **Restoration Notification**: When sensor changes from stopping → not stopping
   - Sends ONE email with subject: "Hydrawise - IRRIGATION RESTORED"
   - Informs user that automatic watering has resumed
   - Marks notification as sent in database

2. **No Duplicate Restoration Emails**: After restoration email is sent
   - No more emails until sensor activates again
   - Tracks notification status in `status_changes` table

3. **Preserved Existing Behavior**: Sensor actively stopping irrigation
   - Continues to send critical alerts on EVERY collection run
   - This is intentional - ongoing critical situation requires repeated alerts

4. **Reset Logic**: When sensor activates again
   - Clears the restoration notification flag
   - Next deactivation can trigger a new restoration email

## Files Modified

### 1. `irrigation_tracking_system.py`

**Method**: `_check_sensor_status_change()` (lines 463-538)

**Changes**:
- Changed return type from `bool` to `Dict[str, Any]`
- Now writes sensor status changes to `status_changes` table
- Records change type: `SENSOR_ACTIVATED` or `SENSOR_DEACTIVATED`
- Returns detailed change information including change ID for tracking

**Method**: `collect_sensor_status()` (lines 161-176)

**Changes**:
- Updated to handle new dict return from `_check_sensor_status_change()`
- Stores change information in `sensor_info` dict for downstream use
- Passes change type and ID to email logic

### 2. `utils/comprehensive_status_monitor.py`

**Method**: `should_send_immediate_email()` (lines 318-377)

**Changes**:
- Added parameters: `sensor_change_type`, `sensor_change_id`
- Implemented priority-based email decision logic:
  1. Sensor actively stopping (ongoing) → send every time
  2. Sensor deactivated (restoration) → send once if not already sent
  3. Sensor activated → send alert
  4. Significant zone changes → send based on severity
- Checks database to prevent duplicate restoration notifications

**New Methods Added**:

- `_check_restoration_notification_sent()` (lines 379-418)
  - Queries `status_changes` table to check if restoration email already sent
  - Prevents duplicate notifications for same restoration period

- `_mark_restoration_notification_sent()` (lines 420-442)
  - Updates `status_changes` record to mark notification as sent
  - Records timestamp and notification method

- `_mark_restoration_notification_reset()` (lines 444-456)
  - Logs when sensor activates (enables future restoration notifications)
  - Reset is automatic via database - new SENSOR_ACTIVATED record starts fresh cycle

**Method**: `generate_comprehensive_email_content()` (lines 464-552)

**Changes**:
- Added parameter: `sensor_change_type`
- Generates three different email types based on sensor status:
  1. **Restoration email**: "IRRIGATION RESTORED" with good news message
  2. **Activation email**: "RAIN SENSOR ACTIVATED" with critical warning
  3. **Ongoing alert email**: Repeated critical alerts while sensor is active
- Clear, user-friendly messages explaining what happened and what to expect

**Function**: `integrate_comprehensive_monitoring()` (lines 555-600)

**Changes**:
- Extracts sensor change info from `sensor_info` dict
- Passes change type and ID to email decision logic
- Marks restoration notification as sent after email is generated

## Database Usage

### Table: `status_changes`

**Records Created**:
- `SENSOR_ACTIVATED`: When sensor starts stopping irrigation
- `SENSOR_DEACTIVATED`: When sensor stops stopping irrigation

**Fields Used**:
- `change_type`: Type of change
- `change_date`: Date change occurred
- `previous_value`: Previous stopping status
- `new_value`: Current stopping status
- `change_description`: Human-readable description
- `sensor_status`: Raw sensor status text
- `notification_sent`: Boolean flag - TRUE after restoration email sent
- `notification_sent_at`: Timestamp of notification
- `notification_method`: Always 'email'
- `detected_at`: When change was detected

## Testing Recommendations

### Test Scenario 1: Sensor Activates (Starts Stopping)
1. Start with sensor not stopping irrigation
2. Activate rain sensor (or wait for rain)
3. **Expected**: Receive critical alert email immediately
4. Run collection again (sensor still stopping)
5. **Expected**: Receive another critical alert email (ongoing)

### Test Scenario 2: Sensor Deactivates (Restoration)
1. Start with sensor actively stopping irrigation
2. Deactivate rain sensor (sensor dries)
3. **Expected**: Receive "IRRIGATION RESTORED" email once
4. Run collection again (sensor still not stopping)
5. **Expected**: NO email (restoration already notified)
6. Run collection multiple times
7. **Expected**: NO emails (sensor still not stopping)

### Test Scenario 3: Full Cycle
1. Sensor activates → **Email sent** (critical alert)
2. Collection runs → **Emails sent** (repeated critical alerts)
3. Sensor deactivates → **Email sent** (restoration)
4. Collection runs → **No emails** (restoration already notified)
5. Sensor activates again → **Email sent** (new critical alert)
6. Sensor deactivates again → **Email sent** (new restoration)

## Rollback Instructions

If issues arise, rollback to v4.3.11:

```bash
git checkout v4.3.11
```

Or view the backup commit:
```bash
git show v4.3.11
```

## Success Criteria

✅ Restoration email sent exactly once when sensor deactivates
✅ Ongoing critical alerts still sent every time while sensor is active
✅ No duplicate restoration emails during same non-stopping period
✅ New restoration email sent after sensor activates and deactivates again
✅ Clear, informative email content for all scenarios
✅ Database properly tracks notification status
✅ No regression in existing functionality

## Notes

- All email content uses ASCII-safe characters (no Unicode emojis in code) per user's cloud deployment requirements
- Houston time zone used for all timestamps
- Inline programmer documentation maintained in all modified code
- No changes to automated_collector.py or data collection logic
- Existing functionality preserved - only report generation modified

