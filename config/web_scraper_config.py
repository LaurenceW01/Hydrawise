#!/usr/bin/env python3
"""
Web Scraper Configuration

Configuration settings for the Hydrawise web portal scraper including
selectors, timeouts, and parsing rules.

Author: AI Assistant
Date: 2025
"""

# CSS Selectors and XPath expressions for Hydrawise portal elements
SELECTORS = {
    # Login page elements  
    'login': {
        'email_field': '//input[@placeholder="Email"]',
        'password_field': '//input[@placeholder="Password"]', 
        'submit_button': '//button[contains(text(), "Log in")]',
        'login_form': 'form'
    },
    
    # Reports page elements (based on actual HTML inspection)
    'reports': {
        'schedule_tab': "//div[@data-testid='sub-tab-reports.name.watering-schedule']",
        'reported_tab': "//div[@data-testid='sub-tab-reports.name.watering-history']", 
        'water_savings_tab': "//div[@data-testid='sub-tab-reports.name.water-saving']",
        'schedule_tab_alt': "//div[contains(@class, 'reports-page__subtabs__tab') and contains(text(), 'Schedule')]",
        'reported_tab_alt': "//div[contains(@class, 'reports-page__subtabs__tab') and contains(text(), 'Reported')]",
        'day_button': '//button[contains(text(), "Day")]',
        'week_button': '//button[contains(text(), "Week")]',
        'month_button': '//button[contains(text(), "Month")]',
        'today_button': '//button[contains(text(), "Today")]',
        'previous_button': '//button[contains(text(), "Previous")]',
        'next_button': '//button[contains(text(), "Next")]'
    },
    
    # Timeline elements
    'timeline': {
        'zone_blocks': '.timeline-block',
        'zone_names': '.zone-name',
        'time_labels': '.time-label',
        'popup': '.tooltip, .popup-content, .hover-popup'
    },
    
    # Date navigation
    'navigation': {
        'prev_day': '.nav-prev, .previous-day',
        'next_day': '.nav-next, .next-day',
        'date_picker': '.date-picker, input[type="date"]',
        'today_button': '.today-btn, .current-day'
    }
}

# Timeout settings (in seconds)
TIMEOUTS = {
    'page_load': 30,
    'element_wait': 20,
    'popup_wait': 3,
    'hover_delay': 1,
    'tab_switch_delay': 2,
    'login_wait': 10
}

# URL patterns
URLS = {
    'base': 'https://app.hydrawise.com',
    'login': 'https://app.hydrawise.com/config/login',
    'reports': 'https://app.hydrawise.com/config/reports',
    'dashboard': 'https://app.hydrawise.com/config/dashboard'
}

# Browser settings
BROWSER_CONFIG = {
    'window_size': (1920, 1080),
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'headless': True,  # Set to False for debugging
    'implicit_wait': 10,
    'page_load_timeout': 30
}

# Data parsing patterns
PARSING_PATTERNS = {
    # Regex patterns for extracting data from popup text
    'duration': r'(\d+)\s*(?:minutes?|mins?|min)',
    'gallons': r'(\d+\.?\d*)\s*gallons?',
    'time': r'(\d{1,2}):(\d{2})\s*(?:AM|PM)?',
    'water_usage': r'Water usage:\s*(\d+\.?\d*)\s*Gallons',
    'current_reading': r'Current:\s*(\d+\.?\d*)mA',
    'duration_reading': r'Duration:\s*(\d+)\s*minutes?'
}

# Status patterns for identifying failure types
FAILURE_PATTERNS = {
    'sensor_abort': [
        'aborted due to sensor input',
        'sensor failure',
        'flow sensor error'
    ],
    'cancelled': [
        'cancelled due to manual start',
        'watering cancelled',
        'cycle cancelled'
    ],
    'suspended': [
        'watering cycle suspended',
        'system suspended',
        'temporarily suspended'
    ],
    'weather_skip': [
        'skipped due to rain',
        'weather delay',
        'rain sensor active'
    ],
    'reduced': [
        'reduced watering due to temperature',
        'watering time reduced',
        'shortened due to weather'
    ],
    'extended': [
        'extended watering time due to temperature',
        'watering time extended',
        'extended due to heat'
    ]
}

# Zone priority mappings (can be customized based on your specific zones)
ZONE_PRIORITIES = {
    # High priority zones (trees, expensive plants)
    'high': [
        'Front Planters',
        'Rear Left Pots', 
        'Rear Right Pots',
        'Rear Left Beds at Fence',
        'Rear Right Beds at Fence',
        'Front Color'
    ],
    
    # Medium priority zones (established landscaping)
    'medium': [
        'Front Right Bed',
        'Rear Right Bed at House',
        'Rear Left Bed at House',
        'Rear Bed/Planters at Pool',
        'Front Left Beds'
    ],
    
    # Lower priority zones (turf areas)
    'low': [
        'Front Right Turf',
        'Front Turf Across',
        'Front Left Turf',
        'Left Side Turf',
        'Rear Left Turf',
        'Rear Right Turf'
    ]
}

# Alert thresholds
ALERT_THRESHOLDS = {
    'critical': {
        'missed_run_hours': 1,      # Alert if zone missed run by more than 1 hour
        'sensor_abort_immediate': True,  # Immediate alert for sensor failures
        'water_variance_percent': 50,    # Alert if water delivery is 50%+ off
        'high_priority_delay_hours': 2   # Alert for high priority zones delayed 2+ hours
    },
    
    'warning': {
        'water_variance_percent': 30,    # Warning if water delivery is 30%+ off
        'duration_variance_percent': 25, # Warning if duration is 25%+ off
        'medium_priority_delay_hours': 4, # Warning for medium priority delays
        'low_priority_delay_hours': 8    # Warning for low priority delays
    }
}

# Retry settings
RETRY_CONFIG = {
    'max_attempts': 3,
    'retry_delay': 5,
    'login_retries': 2,
    'element_find_retries': 3,
    'popup_extract_retries': 2
}

def get_zone_priority(zone_name: str) -> str:
    """
    Determine zone priority based on name.
    
    Args:
        zone_name (str): Name of the zone
        
    Returns:
        str: Priority level ('high', 'medium', 'low')
    """
    zone_name_lower = zone_name.lower()
    
    # Check high priority zones
    for high_zone in ZONE_PRIORITIES['high']:
        if high_zone.lower() in zone_name_lower:
            return 'high'
            
    # Check medium priority zones  
    for medium_zone in ZONE_PRIORITIES['medium']:
        if medium_zone.lower() in zone_name_lower:
            return 'medium'
            
    # Default to low priority
    return 'low'

def detect_failure_type(status_text: str) -> str:
    """
    Detect failure type from status text.
    
    Args:
        status_text (str): Status text from popup or logs
        
    Returns:
        str: Failure type identifier
    """
    status_lower = status_text.lower()
    
    for failure_type, patterns in FAILURE_PATTERNS.items():
        for pattern in patterns:
            if pattern in status_lower:
                return failure_type
                
    return 'unknown'

if __name__ == "__main__":
    print("Hydrawise Web Scraper Configuration")
    print("=" * 50)
    
    print(f"\nBase URL: {URLS['base']}")
    print(f"Browser headless: {BROWSER_CONFIG['headless']}")
    print(f"Page load timeout: {TIMEOUTS['page_load']}s")
    
    print(f"\nZone Priorities:")
    for priority, zones in ZONE_PRIORITIES.items():
        print(f"  {priority.upper()}: {len(zones)} zones")
        for zone in zones[:3]:  # Show first 3
            print(f"    - {zone}")
        if len(zones) > 3:
            print(f"    ... and {len(zones)-3} more")
            
    print(f"\nFailure Patterns:")
    for failure_type, patterns in FAILURE_PATTERNS.items():
        print(f"  {failure_type}: {len(patterns)} patterns")
        
    # Test zone priority detection
    test_zones = ["Front Planters and Pots", "Rear Left Turf", "Front Right Bed"]
    print(f"\nTest Zone Priority Detection:")
    for zone in test_zones:
        priority = get_zone_priority(zone)
        print(f"  {zone}: {priority.upper()}")
