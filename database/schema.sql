-- Hydrawise Irrigation Data Collection Database Schema
-- SQLite compatible schema for irrigation monitoring and analysis
-- Created: 2025-08-21

-- =====================================================
-- CORE TABLES: Schedule and Actual Run Data
-- =====================================================

-- Zones table: Master list of irrigation zones
CREATE TABLE zones (
    zone_id INTEGER PRIMARY KEY,
    zone_name TEXT NOT NULL UNIQUE,
    zone_display_name TEXT,  -- Full name from web scraper
    priority_level TEXT CHECK (priority_level IN ('HIGH', 'MEDIUM', 'LOW')) DEFAULT 'MEDIUM',
    flow_rate_gpm REAL,  -- Gallons per minute from flow rate measurements
    average_flow_rate REAL,  -- Average flow rate for water usage estimation (GPM)
    typical_duration_minutes INTEGER DEFAULT 3,
    plant_type TEXT,  -- e.g., 'planters', 'beds', 'turf', 'color'
    install_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Scheduled runs: What the system plans to do
CREATE TABLE scheduled_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    zone_name TEXT NOT NULL,  -- Denormalized for easier queries
    schedule_date DATE NOT NULL,
    scheduled_start_time TIMESTAMP NOT NULL,
    scheduled_duration_minutes INTEGER NOT NULL,
    expected_gallons REAL,  -- Calculated: flow_rate * duration
    program_name TEXT,  -- If available from scraper
    source TEXT DEFAULT 'web_scraper' CHECK (source IN ('web_scraper', 'api', 'manual')),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    raw_popup_text TEXT,  -- Complete popup text from hover
    popup_lines_json TEXT,  -- JSON array of parsed popup lines with type/value
    parsed_summary TEXT,  -- Summary of key parsed data
    is_rain_cancelled BOOLEAN DEFAULT FALSE,  -- True if "Not scheduled to run" due to rain
    rain_sensor_status TEXT,  -- Rain sensor related status text
    popup_status TEXT,  -- Full status from popup
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
    UNIQUE(zone_id, scheduled_start_time)  -- Prevent duplicate scheduled runs
);

-- Actual runs: What actually happened
CREATE TABLE actual_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id INTEGER NOT NULL,
    zone_name TEXT NOT NULL,  -- Denormalized for easier queries
    run_date DATE NOT NULL,
    actual_start_time TIMESTAMP NOT NULL,
    actual_duration_minutes REAL NOT NULL,
    actual_gallons REAL,  -- From hover popup data
    status TEXT NOT NULL DEFAULT 'Normal watering cycle',
    failure_reason TEXT,  -- e.g., 'Aborted due to sensor input'
    current_ma REAL,  -- Current reading in milliamps (changed to REAL for decimals)
    end_time TIMESTAMP,  -- Calculated: start_time + duration
    source TEXT DEFAULT 'web_scraper' CHECK (source IN ('web_scraper', 'api', 'manual')),
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    raw_popup_text TEXT,  -- Complete popup text from hover
    popup_lines_json TEXT,  -- JSON array of parsed popup lines with type/value
    parsed_summary TEXT,  -- Summary of key parsed data
    water_efficiency REAL,  -- Percentage: (actual/expected) * 100
    abort_reason TEXT,  -- Specific abort reason if run was aborted
    usage_type TEXT CHECK (usage_type IN ('actual', 'estimated')) DEFAULT 'actual',  -- Water usage estimation type
    usage REAL,  -- Contains either actual_gallons or estimated value for analysis
    usage_flag TEXT CHECK (usage_flag IN ('normal', 'too_high', 'too_low', 'zero_reported')) DEFAULT 'normal',  -- Flag for unusual consumption
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
    UNIQUE(zone_id, actual_start_time)  -- Prevent duplicate actual runs
);

-- =====================================================
-- ANALYSIS TABLES: Variance and Pattern Detection
-- =====================================================

-- Daily variance analysis: Scheduled vs Actual comparison
CREATE TABLE daily_variance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date DATE NOT NULL,
    zone_id INTEGER NOT NULL,
    zone_name TEXT NOT NULL,
    
    -- Scheduled totals for the day
    scheduled_runs_count INTEGER DEFAULT 0,
    scheduled_total_minutes INTEGER DEFAULT 0,
    scheduled_total_gallons REAL DEFAULT 0,
    
    -- Actual totals for the day
    actual_runs_count INTEGER DEFAULT 0,
    actual_total_minutes INTEGER DEFAULT 0,
    actual_total_gallons REAL DEFAULT 0,
    
    -- Variance calculations
    run_count_variance INTEGER,  -- actual - scheduled
    duration_variance_minutes INTEGER,  -- actual - scheduled
    water_variance_gallons REAL,  -- actual - scheduled
    water_efficiency_percent REAL,  -- (actual/scheduled) * 100
    
    -- Status flags
    has_failures BOOLEAN DEFAULT FALSE,
    has_warnings BOOLEAN DEFAULT FALSE,
    variance_severity TEXT CHECK (variance_severity IN ('NORMAL', 'WARNING', 'CRITICAL')) DEFAULT 'NORMAL',
    
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
    UNIQUE(analysis_date, zone_id)
);

-- Failure events: Detected irrigation problems
CREATE TABLE failure_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    failure_id TEXT UNIQUE NOT NULL,  -- e.g., 'missing_Front_Planters_1830'
    zone_id INTEGER NOT NULL,
    zone_name TEXT NOT NULL,
    failure_date DATE NOT NULL,
    failure_type TEXT NOT NULL CHECK (failure_type IN (
        'MISSING_RUN', 'UNEXPECTED_RUN', 'FAILED_RUN', 
        'WATER_VARIANCE', 'DURATION_VARIANCE', 'SENSOR_ABORT'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'WARNING', 'INFO')),
    description TEXT NOT NULL,
    recommended_action TEXT,
    plant_risk TEXT CHECK (plant_risk IN ('HIGH', 'MEDIUM', 'LOW')),
    max_hours_without_water INTEGER,
    
    -- Associated run data
    scheduled_run_id INTEGER,  -- Link to scheduled_runs table
    actual_run_id INTEGER,     -- Link to actual_runs table
    
    -- Failure details
    scheduled_gallons REAL,
    actual_gallons REAL,
    water_deficit REAL,
    hours_since_last_water REAL,
    
    -- Resolution tracking
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolution_method TEXT,  -- 'manual_run', 'auto_recovery', 'weather_delay'
    resolution_notes TEXT,
    
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
    FOREIGN KEY (scheduled_run_id) REFERENCES scheduled_runs(id),
    FOREIGN KEY (actual_run_id) REFERENCES actual_runs(id)
);

-- =====================================================
-- OPERATIONAL TABLES: System Monitoring
-- =====================================================

-- Data collection log: Track scraping operations
CREATE TABLE collection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_date DATE NOT NULL,
    collection_type TEXT NOT NULL CHECK (collection_type IN ('daily_scrape', 'historical_backfill', 'excel_import')),
    status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    
    -- Data collected
    scheduled_runs_collected INTEGER DEFAULT 0,
    actual_runs_collected INTEGER DEFAULT 0,
    zones_processed INTEGER DEFAULT 0,
    
    -- Processing details
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    processing_duration_seconds INTEGER,
    
    -- Error handling
    errors_encountered INTEGER DEFAULT 0,
    error_details TEXT,
    warnings TEXT,
    
    -- Source information
    source_url TEXT,
    scraper_version TEXT,
    browser_info TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System status: Current operational state
CREATE TABLE system_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status_date DATE NOT NULL UNIQUE,
    overall_status TEXT NOT NULL CHECK (overall_status IN ('HEALTHY', 'DEGRADED', 'CRITICAL')),
    
    -- System metrics
    total_zones INTEGER,
    zones_running_normally INTEGER,
    zones_with_warnings INTEGER,
    zones_with_failures INTEGER,
    
    -- Water metrics
    total_water_scheduled REAL,
    total_water_delivered REAL,
    water_efficiency_percent REAL,
    
    -- Alert counts
    critical_alerts INTEGER DEFAULT 0,
    warning_alerts INTEGER DEFAULT 0,
    info_alerts INTEGER DEFAULT 0,
    
    -- Last data collection
    last_schedule_scrape TIMESTAMP,
    last_actual_scrape TIMESTAMP,
    next_collection_due TIMESTAMP,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- HISTORICAL INTEGRATION: Excel Data Import
-- =====================================================

-- Excel import log: Track historical data integration
CREATE TABLE excel_import_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_name TEXT NOT NULL,
    file_type TEXT CHECK (file_type IN ('watering_report', 'schedule_report')),
    file_hash TEXT,  -- MD5 hash to prevent duplicate imports
    
    -- Import results
    rows_processed INTEGER,
    rows_imported INTEGER,
    rows_skipped INTEGER,
    errors_encountered INTEGER,
    
    -- Date range covered
    data_start_date DATE,
    data_end_date DATE,
    
    import_status TEXT CHECK (import_status IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    error_details TEXT,
    notes TEXT
);

-- Historical notes: Operational context from Excel files
CREATE TABLE historical_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_date DATE NOT NULL,
    zone_id INTEGER,
    zone_name TEXT,
    note_type TEXT CHECK (note_type IN ('operational', 'maintenance', 'weather', 'system')),
    note_text TEXT NOT NULL,
    source TEXT DEFAULT 'excel_import',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

-- =====================================================
-- INDEXES: Optimize query performance
-- =====================================================

-- Primary query indexes
CREATE INDEX idx_scheduled_runs_date_zone ON scheduled_runs(schedule_date, zone_id);
CREATE INDEX idx_actual_runs_date_zone ON actual_runs(run_date, zone_id);
CREATE INDEX idx_daily_variance_date_zone ON daily_variance(analysis_date, zone_id);
CREATE INDEX idx_failure_events_date_severity ON failure_events(failure_date, severity);

-- Time-based indexes for analysis
CREATE INDEX idx_scheduled_runs_start_time ON scheduled_runs(scheduled_start_time);
CREATE INDEX idx_actual_runs_start_time ON actual_runs(actual_start_time);
CREATE INDEX idx_failure_events_detected_at ON failure_events(detected_at);

-- Status and monitoring indexes
CREATE INDEX idx_collection_log_date_status ON collection_log(collection_date, status);
CREATE INDEX idx_system_status_date ON system_status(status_date);

-- =====================================================
-- VIEWS: Simplified data access for analysis
-- =====================================================

-- Current day irrigation summary
CREATE VIEW v_daily_summary AS
SELECT 
    date('now') as today,
    z.zone_name,
    z.priority_level,
    
    -- Scheduled data
    COUNT(DISTINCT sr.id) as scheduled_runs,
    COALESCE(SUM(sr.scheduled_duration_minutes), 0) as scheduled_minutes,
    COALESCE(SUM(sr.expected_gallons), 0) as scheduled_gallons,
    
    -- Actual data  
    COUNT(DISTINCT ar.id) as actual_runs,
    COALESCE(SUM(ar.actual_duration_minutes), 0) as actual_minutes,
    COALESCE(SUM(ar.actual_gallons), 0) as actual_gallons,
    
    -- Variance
    (COUNT(DISTINCT ar.id) - COUNT(DISTINCT sr.id)) as run_variance,
    (COALESCE(SUM(ar.actual_gallons), 0) - COALESCE(SUM(sr.expected_gallons), 0)) as water_variance
    
FROM zones z
LEFT JOIN scheduled_runs sr ON z.zone_id = sr.zone_id AND sr.schedule_date = date('now')
LEFT JOIN actual_runs ar ON z.zone_id = ar.zone_id AND ar.run_date = date('now')
GROUP BY z.zone_id, z.zone_name, z.priority_level;

-- Active failures requiring attention
CREATE VIEW v_active_failures AS
SELECT 
    fe.*,
    z.priority_level,
    z.flow_rate_gpm,
    CASE 
        WHEN fe.detected_at > datetime('now', '-1 hour') THEN 'IMMEDIATE'
        WHEN fe.detected_at > datetime('now', '-6 hours') THEN 'URGENT' 
        ELSE 'REVIEW'
    END as urgency_level
FROM failure_events fe
JOIN zones z ON fe.zone_id = z.zone_id
WHERE fe.resolved = FALSE
ORDER BY 
    CASE fe.severity 
        WHEN 'CRITICAL' THEN 1 
        WHEN 'WARNING' THEN 2 
        ELSE 3 
    END,
    fe.detected_at DESC;

-- Zone performance summary (last 30 days)
CREATE VIEW v_zone_performance AS
SELECT 
    z.zone_name,
    z.priority_level,
    COUNT(DISTINCT dv.analysis_date) as days_analyzed,
    AVG(dv.water_efficiency_percent) as avg_efficiency,
    SUM(CASE WHEN dv.variance_severity = 'CRITICAL' THEN 1 ELSE 0 END) as critical_days,
    SUM(CASE WHEN dv.variance_severity = 'WARNING' THEN 1 ELSE 0 END) as warning_days,
    AVG(dv.water_variance_gallons) as avg_water_variance,
    MAX(dv.analyzed_at) as last_analysis
FROM zones z
LEFT JOIN daily_variance dv ON z.zone_id = dv.zone_id 
    AND dv.analysis_date >= date('now', '-30 days')
GROUP BY z.zone_id, z.zone_name, z.priority_level;
