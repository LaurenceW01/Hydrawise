# Rain Sensor and Status Change Tracking Requirements

## Overview

This document outlines the requirements for implementing comprehensive rain sensor monitoring and scheduled run status change tracking in the Hydrawise automated collector system. The system must detect, track, and report critical irrigation events that prevent zones from receiving water.

## Background

The Hydrawise irrigation controller has several mechanisms that can prevent scheduled irrigation:

1. **Rain Sensor Status**: Hardware sensor that stops irrigation when wet
2. **High Daily Rainfall**: System-calculated rainfall threshold that aborts runs  
3. **Sensor Input Failures**: Hardware sensor malfunctions that abort runs
4. **User Zone Suspensions**: Manual user actions that suspend zones

These events are critical because they prevent irrigation, potentially impacting plant health. Currently, these events are not systematically tracked or reported.

## Critical Requirements

### 1. Rain Sensor Status Tracking

**Current State**: Rain sensor detection exists in `sensor_detector.py` but is not integrated into automated collection.

**Requirements**:
- Detect rain sensor status on every automated collection run (startup, daily, interval)
- Track sensor status changes: "Sensor is stopping irrigation" ↔ "Sensor is not stopping irrigation"
- Store sensor status history with Houston timezone timestamps
- Log sensor status changes immediately when detected
- Email notification when sensor status changes (max 1 email per day)

**Data to Capture**:
- Sensor status text from dashboard
- Whether irrigation is currently suspended
- Timestamp of status detection
- Duration of sensor active periods

### 2. Scheduled Run Status Change Detection

**Critical Insight**: Status changes must be detected by comparing current scheduled runs against the **most recent recorded run for each zone**, regardless of date/time.

**Status Types to Track**:
1. **Normal Operation**: "Normal watering cycle" + timing information
2. **High Rainfall Abort**: "Aborted due to high daily rainfall" 
3. **Sensor Input Abort**: "Aborted due to sensor input"
4. **User Suspension**: "Water cycle suspended"
5. **Not Scheduled**: "Not scheduled to run" (generic)

**Change Detection Logic**:
- Compare each current run's popup text against most recent database record for that zone
- Classify status using priority-based pattern matching (avoid false positives from timing info)
- Detect transitions between any status types
- Store complete change history with before/after states

**Critical Classification Rules**:
```
Priority 1 (Most Specific):
- "aborted due to high daily rainfall" → rainfall_abort
- "aborted due to sensor input" → sensor_abort  
- "water cycle suspended" → user_suspended
- "not scheduled to run" → not_scheduled

Priority 2 (Explicit Normal):
- "normal watering cycle" → normal_cycle

Priority 3 (Fallback Logic):
- Contains "time:" AND "duration:" WITHOUT abort keywords → normal_cycle
- Contains abort/cancel keywords → other_abort
- Default → unknown
```

### 3. Email Notification System

**Requirements**:
- Maximum 1 email per day when changes are detected
- Email only sent if status changes occurred during collection
- Configurable recipient list
- Daily summary format at configurable time (default 7:00 PM Houston)
- Immediate notification for critical sensor changes

**Email Content Requirements**:
- Group changes by type (rainfall, sensor, user suspension, restoration)
- Show affected zones and expected water loss
- Include timing of changes
- Show comparison dates (what previous run was compared against)
- Summary totals (zones affected, gallons prevented)

### 4. Database Schema Requirements

#### Rain Sensor Status History Table
```sql
CREATE TABLE rain_sensor_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status_date DATE NOT NULL,
    status_time TIMESTAMP NOT NULL,
    sensor_status TEXT NOT NULL,
    is_stopping_irrigation BOOLEAN NOT NULL,
    irrigation_suspended BOOLEAN NOT NULL,
    sensor_text_raw TEXT,
    collection_run_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(status_date, status_time)
);
```

#### Scheduled Run Status Changes Table  
```sql
CREATE TABLE scheduled_run_status_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    zone_name TEXT NOT NULL,
    
    -- Detection timing
    change_detected_date DATE NOT NULL,
    change_detected_time TIMESTAMP NOT NULL,
    collection_run_id TEXT,
    
    -- Current run (from web scraping)
    current_run_date DATE NOT NULL,
    current_scheduled_start_time TIMESTAMP NOT NULL,
    current_status_type TEXT NOT NULL,
    current_popup_text TEXT,
    
    -- Previous run (from database comparison)
    previous_run_date DATE NOT NULL,
    previous_scheduled_start_time TIMESTAMP NOT NULL,
    previous_status_type TEXT NOT NULL,
    previous_popup_text TEXT,
    
    -- Change analysis
    change_type TEXT NOT NULL CHECK (change_type IN (
        'rainfall_abort', 'sensor_abort', 'user_suspended', 
        'normal_restored', 'other_change'
    )),
    irrigation_prevented BOOLEAN DEFAULT TRUE,
    expected_gallons_lost REAL DEFAULT 0,
    time_since_last_record_hours REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);
```

#### Daily Status Summary Table
```sql
CREATE TABLE daily_status_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date DATE NOT NULL UNIQUE,
    
    -- Change counts by type
    rainfall_aborts_count INTEGER DEFAULT 0,
    sensor_aborts_count INTEGER DEFAULT 0,
    user_suspensions_count INTEGER DEFAULT 0,
    normal_restorations_count INTEGER DEFAULT 0,
    total_changes_count INTEGER DEFAULT 0,
    
    -- Impact summary
    zones_affected_count INTEGER DEFAULT 0,
    total_gallons_lost REAL DEFAULT 0,
    irrigation_runs_prevented INTEGER DEFAULT 0,
    
    -- Sensor context
    sensor_stopping_periods INTEGER DEFAULT 0,
    sensor_active_duration_minutes INTEGER DEFAULT 0,
    
    -- Notification tracking
    email_notification_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP,
    email_recipients TEXT,
    
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Email Notifications Log Table
```sql
CREATE TABLE email_notifications_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_date DATE NOT NULL,
    notification_type TEXT NOT NULL CHECK (notification_type IN (
        'sensor_change', 'daily_summary', 'status_changes'
    )),
    trigger_event TEXT NOT NULL,
    recipients TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_preview TEXT,
    affected_zones TEXT,
    sensor_status_changed BOOLEAN DEFAULT FALSE,
    runs_affected_count INTEGER DEFAULT 0,
    email_sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5. Configuration Requirements

**Enhanced ScheduleConfig**:
```python
@dataclass
class ScheduleConfig:
    # ... existing fields ...
    
    # Email notification settings
    email_notifications_enabled: bool = True
    notification_recipients: List[str] = field(default_factory=list)
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    
    # Notification types
    sensor_change_notifications: bool = True
    status_change_notifications: bool = True
    daily_summary_notifications: bool = True
    
    # Timing and limits
    daily_summary_time: dt_time = dt_time(19, 0)  # 7:00 PM Houston
    max_emails_per_day: int = 1
    
    # Sensor tracking
    track_sensor_status: bool = True
    track_status_changes: bool = True
```

### 6. Integration Requirements

**Automated Collector Integration**:
- Add sensor status collection to every collection run (startup, daily, interval)
- Add status change detection to scheduled run collection
- Integrate email notifications into collection loop
- Maintain existing collection functionality without disruption
- Add comprehensive logging for all detection events

**Collection Flow Enhancement**:
1. Collect rain sensor status from dashboard
2. Collect scheduled runs from web interface  
3. Compare each run against most recent database record for that zone
4. Detect and classify status changes
5. Store new runs and status changes in database
6. Check daily email eligibility and send if needed
7. Log all activities with Houston timestamps

### 7. Critical Detection Scenarios

**Scenario 1: High Rainfall Event**
```
Previous: "Normal watering cycle\nTime: Thu, 7:05am\nDuration: 1 minute"
Current:  "Aborted due to high daily rainfall\nTime: Thu, 7:05am\nDuration: Not scheduled to run"
Detection: normal_cycle → rainfall_abort
Action: Store change, send email if first of day
```

**Scenario 2: Sensor Failure**  
```
Previous: "Normal watering cycle\nTime: Thu, 7:05am\nDuration: 1 minute"
Current:  "Aborted due to sensor input\nTime: Thu, 7:05am\nDuration: Not scheduled to run"
Detection: normal_cycle → sensor_abort
Action: Store change, send email if first of day
```

**Scenario 3: User Suspension**
```
Previous: "Normal watering cycle\nTime: Thu, 7:05am\nDuration: 1 minute"
Current:  "Water cycle suspended\nTime: Thu, 7:05am\nDuration: Not scheduled to run"
Detection: normal_cycle → user_suspended
Action: Store change, send email if first of day
```

**Scenario 4: Restoration**
```
Previous: "Aborted due to sensor input\nTime: Thu, 7:05am\nDuration: Not scheduled to run"
Current:  "Normal watering cycle\nTime: Thu, 7:05am\nDuration: 1 minute"
Detection: sensor_abort → normal_cycle
Action: Store change, send email if first of day
```

### 8. Email Template Requirements

**Daily Summary Email Template**:
```
Subject: Hydrawise Status Changes - [Date] - [X] zones affected

STATUS CHANGES DETECTED:

🌧️ HIGH RAINFALL ABORTS (X zones):
- Zone Name: Scheduled Time (Expected Gallons)
- Status: "Aborted due to high daily rainfall"

🔧 SENSOR INPUT ABORTS (X zones):  
- Zone Name: Scheduled Time (Expected Gallons)
- Status: "Aborted due to sensor input"

⏸️ USER SUSPENSIONS (X zones):
- Zone Name: Scheduled Time (Expected Gallons) 
- Status: "Water cycle suspended"

✅ NORMAL OPERATION RESTORED (X zones):
- Zone Name: Restored to normal watering

SUMMARY:
- Total zones affected: X
- Total water prevented: X.X gallons
- Detection time: [Houston Time]
- Next collection: [Next Day] 6:00 AM

This is an automated notification sent once daily when changes are detected.
```

### 9. Success Criteria

**System must successfully**:
1. Detect rain sensor status changes within 5 minutes of occurrence
2. Detect scheduled run status changes on every collection cycle
3. Store complete change history with Houston timestamps  
4. Send email notifications within 10 minutes of detection
5. Prevent duplicate emails (max 1 per day)
6. Maintain 99% uptime for automated collection
7. Handle missing or malformed popup data gracefully
8. Provide comprehensive logging for troubleshooting

**Reporting Requirements**:
1. Daily summary reports of all changes
2. Historical trend analysis of sensor activity
3. Zone-specific irrigation impact reports
4. Email delivery confirmation and error tracking

### 10. Technical Constraints

**Performance**:
- Status change detection must not increase collection time by more than 30 seconds
- Database queries must complete within 5 seconds
- Email sending must be non-blocking to collection process

**Reliability**:
- System must handle web scraping failures gracefully
- Email failures must not break collection process
- Database schema changes must be backward compatible
- All timestamps must use Houston timezone consistently

**Maintenance**:
- Configuration changes must not require system restart
- Email templates must be easily customizable
- Logging must provide sufficient detail for troubleshooting
- Database maintenance must be automated

## Implementation Priority

**Phase 1 (Critical)**:
1. Database schema creation and migration
2. Status change detection logic
3. Basic email notification system

**Phase 2 (Important)**:  
4. Rain sensor integration
5. Enhanced email templates
6. Comprehensive logging

**Phase 3 (Enhancement)**:
7. Reporting dashboard
8. Historical analysis tools
9. Advanced notification rules

This requirements document ensures comprehensive tracking and reporting of all irrigation-impacting events while maintaining system reliability and performance.



