# Fix: Unsent Restoration Notifications

## Issue Identified

After deploying v4.3.12, the restoration email was not sent even though:
- The sensor status had changed from stopping→not stopping earlier that day (13:30:30)
- A SENSOR_DEACTIVATED record existed in the database with `notification_sent=FALSE`
- The automated_collector was running and collecting sensor status correctly

**Root Cause**: The restoration email logic only triggered when a sensor change was detected **in real-time** during a collection run. It did NOT check the database for unsent SENSOR_DEACTIVATED records from previous changes that happened before the code was deployed or when the system was down.

## The Problem

The original logic in `should_send_immediate_email()` was:

```python
# Priority 2: Sensor status changed from stopping to NOT stopping (restoration)
if sensor_status_changed and sensor_change_type == 'SENSOR_DEACTIVATED':
    # Send restoration email
    return True
```

This ONLY worked if `sensor_status_changed=True` for the current collection run. If the sensor had already changed hours ago, `sensor_status_changed=False`, so the restoration email was never triggered.

## The Solution

Added a new check (Priority 2b) that queries the database for unsent restoration notifications:

```python
# Priority 2b: Check for UNSENT restoration notifications in database
if not sensor_status_changed and not critical_alerts:
    unsent_restoration = self._check_for_unsent_restoration()
    if unsent_restoration:
        # Send restoration email for the missed notification
        return True
```

This allows the system to "catch up" on missed notifications.

## Implementation Details

### New Method: `_check_for_unsent_restoration()`

```python
def _check_for_unsent_restoration(self) -> Optional[Dict]:
    """
    Check if there's an unsent SENSOR_DEACTIVATED notification in the database
    
    Returns:
        Dictionary with unsent restoration record info, or None if all notifications sent
    """
```

**Logic**:
1. Query most recent SENSOR_ACTIVATED and SENSOR_DEACTIVATED records
2. If most recent is SENSOR_ACTIVATED → currently in stopping period, no restoration email
3. If most recent is SENSOR_DEACTIVATED with `notification_sent=FALSE` → return the record
4. If most recent is SENSOR_DEACTIVATED with `notification_sent=TRUE` → already notified

### Updated Email Content Generation

The `generate_comprehensive_email_content()` method now accepts an `unsent_restoration_record` parameter and includes a note about delayed notifications:

```
(This restoration occurred at 2025-10-27 13:30:30 but notification was delayed)
```

This helps users understand why they're receiving a notification about a past event.

## Testing Scenario

### Before Fix:
1. Sensor changes from stopping→not stopping at 13:30
2. System is down or code not deployed
3. SENSOR_DEACTIVATED record created in database with notification_sent=FALSE
4. Automated_collector restarts at 15:13
5. Collection runs at 15:26
6. **Result**: No email sent (sensor_status_changed=False)

### After Fix:
1. Sensor changes from stopping→not stopping at 13:30
2. System is down or code not deployed  
3. SENSOR_DEACTIVATED record created in database with notification_sent=FALSE
4. Automated_collector restarts at 15:13
5. Collection runs at 15:26
6. **Result**: Email sent! System finds unsent record in database and sends notification

## Email Behavior Matrix (Updated)

| Scenario | sensor_status_changed | Database Check | Email Action |
|----------|----------------------|----------------|--------------|
| Sensor actively stopping (ongoing) | False | N/A | ✅ Send every time (critical) |
| Sensor just activated (real-time) | True (ACTIVATED) | N/A | ✅ Send once (activation) |
| Sensor just deactivated (real-time) | True (DEACTIVATED) | Check sent status | ✅ Send once if not sent |
| Sensor still not stopping (no change) | False | **Check for unsent** | ✅ Send if unsent found |
| Sensor still not stopping (already notified) | False | Check for unsent | ❌ No email (already sent) |

## Files Modified

- `utils/comprehensive_status_monitor.py`
  - Added `_check_for_unsent_restoration()` method
  - Updated `should_send_immediate_email()` with Priority 2b check
  - Updated `generate_comprehensive_email_content()` to handle unsent records
  - Updated `integrate_comprehensive_monitoring()` to mark unsent records as sent

## Deployment Instructions

1. Commit has been made: `11c17d1`
2. Restart `automated_collector.py`
3. On next collection run:
   - System will find the unsent SENSOR_DEACTIVATED record (ID: 4) from 13:30:30
   - Send restoration email with note about delayed notification
   - Mark record as notification_sent=TRUE
   - Future runs will not send duplicate emails

## Verification

After restarting automated_collector, check logs for:
```
[DATABASE CHECK] Found unsent SENSOR_DEACTIVATED record (ID: 4, detected: 2025-10-27 13:30:30)
[EMAIL DECISION] Sending email: Found unsent restoration notification from 2025-10-27 13:30:30 (catching up)
[EMAIL] Sending comprehensive email: Hydrawise - IRRIGATION RESTORED: Rain sensor no longer blocking watering
[RESTORATION] Marked restoration notification as sent (change ID: 4)
```

## Benefits

1. **Resilient to downtime**: Missed notifications are caught up automatically
2. **No duplicate emails**: Once sent, notification_sent=TRUE prevents repeats
3. **Clear communication**: Email includes timing note for delayed notifications
4. **Automatic recovery**: System self-corrects without manual intervention

## Next Steps

Ready to restart automated_collector.py. The restoration email should be sent on the next collection run.


