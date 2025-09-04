-- Hydrawise Irrigation Data Collection Database Schema - PostgreSQL Version
-- PostgreSQL compatible schema for irrigation monitoring and analysis
-- Converted from SQLite schema for render.com deployment
-- Created: 2025-01-27

-- =====================================================
-- CORE TABLES: Schedule and Actual Run Data
-- =====================================================

-- Zones table: Master list of irrigation zones
CREATE TABLE IF NOT EXISTS zones (
    zone_id SERIAL PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS scheduled_runs (
    id SERIAL PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS actual_runs (
    id SERIAL PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS daily_variance (
    id SERIAL PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS failure_events (
    id SERIAL PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS collection_log (
    id SERIAL PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS system_status (
    id SERIAL PRIMARY KEY,
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
-- COST TRACKING: Water Bill Analysis
-- =====================================================

-- Water rate configurations: Track Houston rate changes over time
CREATE TABLE IF NOT EXISTS water_rate_configs (
    id SERIAL PRIMARY KEY,
    effective_date DATE NOT NULL,
    billing_period_start_day INTEGER DEFAULT 1,
    manual_watering_gallons_per_day REAL DEFAULT 45.0,
    basic_service_water REAL NOT NULL,
    basic_service_wastewater REAL NOT NULL,
    basic_service_total REAL NOT NULL,
    config_json TEXT NOT NULL,  -- Complete rate tier structure as JSON
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(effective_date)
);

-- Billing period cost calculations: Track estimated costs per period
CREATE TABLE IF NOT EXISTS billing_period_costs (
    id SERIAL PRIMARY KEY,
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    calculation_date DATE NOT NULL,  -- Date the calculation was performed
    
    -- Usage data
    irrigation_gallons REAL DEFAULT 0,
    manual_watering_gallons REAL DEFAULT 0,
    total_gallons REAL NOT NULL,
    
    -- Tier information
    usage_tier INTEGER NOT NULL,
    tier_range_min INTEGER NOT NULL,
    tier_range_max INTEGER NOT NULL,
    water_rate_per_gallon REAL NOT NULL,
    wastewater_rate_per_gallon REAL NOT NULL,
    
    -- Cost breakdown
    basic_service_charge REAL NOT NULL,
    water_usage_cost REAL NOT NULL,
    wastewater_usage_cost REAL NOT NULL,
    total_usage_cost REAL NOT NULL,
    estimated_total_cost REAL NOT NULL,
    
    -- Billing period progress
    days_elapsed INTEGER NOT NULL,
    total_days_in_period INTEGER NOT NULL,
    percent_complete REAL NOT NULL,
    
    -- Projections (for partial periods)
    projected_irrigation_gallons REAL,
    projected_manual_gallons REAL,
    projected_total_gallons REAL,
    projected_tier INTEGER,
    projected_total_cost REAL,
    daily_irrigation_average REAL,
    
    -- Reference to rate config used
    rate_config_id INTEGER,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (rate_config_id) REFERENCES water_rate_configs(id),
    UNIQUE(billing_period_start, calculation_date)
);

-- Daily cost snapshots: Track cost progression throughout billing period
CREATE TABLE IF NOT EXISTS daily_cost_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    
    -- Cumulative usage to date
    irrigation_gallons_to_date REAL DEFAULT 0,
    manual_watering_gallons_to_date REAL DEFAULT 0,
    total_gallons_to_date REAL NOT NULL,
    
    -- Current cost
    estimated_cost_to_date REAL NOT NULL,
    usage_tier INTEGER NOT NULL,
    
    -- Daily increments
    daily_irrigation_gallons REAL DEFAULT 0,
    daily_manual_watering_gallons REAL DEFAULT 0,
    daily_cost_increase REAL DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(snapshot_date, billing_period_start)
);

-- Cost analysis events: Track significant cost events and milestones
CREATE TABLE IF NOT EXISTS cost_analysis_events (
    id SERIAL PRIMARY KEY,
    event_date DATE NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'TIER_CHANGE', 'COST_MILESTONE', 'USAGE_ALERT', 'BILLING_PERIOD_END', 
        'PROJECTION_UPDATE', 'RATE_CHANGE'
    )),
    billing_period_start DATE NOT NULL,
    
    -- Event details
    event_description TEXT NOT NULL,
    previous_value REAL,
    current_value REAL,
    threshold_value REAL,
    
    -- Cost context
    total_usage_at_event REAL,
    estimated_cost_at_event REAL,
    tier_at_event INTEGER,
    
    severity TEXT CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')) DEFAULT 'INFO',
    automated BOOLEAN DEFAULT TRUE,
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- HISTORICAL INTEGRATION: Excel Data Import
-- =====================================================

-- Excel import log: Track historical data integration
CREATE TABLE IF NOT EXISTS excel_import_log (
    id SERIAL PRIMARY KEY,
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
CREATE TABLE IF NOT EXISTS historical_notes (
    id SERIAL PRIMARY KEY,
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
-- TRACKING TABLES: Rain Sensor and Status Changes
-- =====================================================

-- Rain sensor status history: Track rain sensor state over time
CREATE TABLE IF NOT EXISTS rain_sensor_status_history (
    id SERIAL PRIMARY KEY,
    status_date DATE NOT NULL,
    sensor_enabled BOOLEAN NOT NULL,
    sensor_active BOOLEAN NOT NULL,
    status_text TEXT,
    raw_status_data TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(status_date, scraped_at)
);

-- Status changes: Track irrigation status changes and notifications
CREATE TABLE IF NOT EXISTS status_changes (
    id SERIAL PRIMARY KEY,
    change_date DATE NOT NULL,
    change_type TEXT NOT NULL CHECK (change_type IN (
        'SENSOR_ENABLED', 'SENSOR_DISABLED', 'SENSOR_ACTIVATED', 'SENSOR_DEACTIVATED',
        'SCHEDULE_CHANGED', 'ZONE_STATUS_CHANGED', 'SYSTEM_STATUS_CHANGED'
    )),
    zone_id INTEGER,
    zone_name TEXT,
    
    -- Change details
    previous_value TEXT,
    new_value TEXT,
    change_description TEXT NOT NULL,
    
    -- Context
    sensor_status TEXT,
    weather_conditions TEXT,
    system_context TEXT,
    
    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_method TEXT,
    notification_recipients TEXT,
    notification_sent_at TIMESTAMP,
    
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

-- =====================================================
-- INDEXES: Optimize query performance
-- =====================================================

-- Primary query indexes
CREATE INDEX IF NOT EXISTS idx_scheduled_runs_date_zone ON scheduled_runs(schedule_date, zone_id);
CREATE INDEX IF NOT EXISTS idx_actual_runs_date_zone ON actual_runs(run_date, zone_id);
CREATE INDEX IF NOT EXISTS idx_daily_variance_date_zone ON daily_variance(analysis_date, zone_id);
CREATE INDEX IF NOT EXISTS idx_failure_events_date_severity ON failure_events(failure_date, severity);

-- Time-based indexes for analysis
CREATE INDEX IF NOT EXISTS idx_scheduled_runs_start_time ON scheduled_runs(scheduled_start_time);
CREATE INDEX IF NOT EXISTS idx_actual_runs_start_time ON actual_runs(actual_start_time);
CREATE INDEX IF NOT EXISTS idx_failure_events_detected_at ON failure_events(detected_at);

-- Status and monitoring indexes
CREATE INDEX IF NOT EXISTS idx_collection_log_date_status ON collection_log(collection_date, status);
CREATE INDEX IF NOT EXISTS idx_system_status_date ON system_status(status_date);

-- Cost tracking indexes
CREATE INDEX IF NOT EXISTS idx_water_rate_configs_effective_date ON water_rate_configs(effective_date);
CREATE INDEX IF NOT EXISTS idx_billing_period_costs_period ON billing_period_costs(billing_period_start, billing_period_end);
CREATE INDEX IF NOT EXISTS idx_billing_period_costs_calc_date ON billing_period_costs(calculation_date);
CREATE INDEX IF NOT EXISTS idx_daily_cost_snapshots_date ON daily_cost_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_daily_cost_snapshots_period ON daily_cost_snapshots(billing_period_start, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_cost_analysis_events_date_type ON cost_analysis_events(event_date, event_type);
CREATE INDEX IF NOT EXISTS idx_cost_analysis_events_period ON cost_analysis_events(billing_period_start, event_date);

-- Tracking indexes
CREATE INDEX IF NOT EXISTS idx_rain_sensor_status_date ON rain_sensor_status_history(status_date);
CREATE INDEX IF NOT EXISTS idx_status_changes_date_type ON status_changes(change_date, change_type);
CREATE INDEX IF NOT EXISTS idx_status_changes_zone ON status_changes(zone_id, change_date);

-- =====================================================
-- VIEWS: Simplified data access for analysis
-- =====================================================

-- Current day irrigation summary
CREATE OR REPLACE VIEW v_daily_summary AS
SELECT 
    CURRENT_DATE as today,
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
LEFT JOIN scheduled_runs sr ON z.zone_id = sr.zone_id AND sr.schedule_date = CURRENT_DATE
LEFT JOIN actual_runs ar ON z.zone_id = ar.zone_id AND ar.run_date = CURRENT_DATE
GROUP BY z.zone_id, z.zone_name, z.priority_level;

-- Active failures requiring attention
CREATE OR REPLACE VIEW v_active_failures AS
SELECT 
    fe.*,
    z.priority_level,
    z.flow_rate_gpm,
    CASE 
        WHEN fe.detected_at > NOW() - INTERVAL '1 hour' THEN 'IMMEDIATE'
        WHEN fe.detected_at > NOW() - INTERVAL '6 hours' THEN 'URGENT' 
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
CREATE OR REPLACE VIEW v_zone_performance AS
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
    AND dv.analysis_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY z.zone_id, z.zone_name, z.priority_level;
