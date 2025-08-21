# Hydrawise Irrigation Monitoring System

An intelligent irrigation failure detection and alert system for Hydrawise controllers that prevents plant loss through proactive monitoring and emergency response capabilities.

## 🎯 Project Status: OPERATIONAL

**Core System**: Irrigation Failure Detection System is **OPERATIONAL**
- ✅ Web scraping authentication and navigation
- ✅ Schedule data extraction (22 zones monitored)
- ✅ Actual run data extraction with water usage
- ✅ Failure detection and alert generation
- ✅ Database storage and management
- ✅ API-based manual zone control for emergencies

## 🚨 Problem Solved

**Critical Issue**: Irrigation systems can fail silently due to:
- Controller power outages
- Sensor malfunctions  
- Schedule changes/cancellations
- Weather station issues
- Network connectivity problems

**Solution**: Real-time monitoring system that detects when zones don't run as scheduled and provides immediate alerts with emergency manual override capabilities.

## 🏗️ System Architecture

### Phase 1: Alert Foundation ✅ COMPLETE
- Web scraping of Hydrawise portal for complete daily schedules
- Real-time comparison of scheduled vs actual irrigation runs
- Intelligent failure detection with severity classification
- Persistent database storage for historical analysis

### Phase 2: Emergency Response (Next)
- Manual zone control via Hydrawise API
- Emergency watering protocols by zone priority
- Real-time alert delivery (email/SMS/push notifications)
- Dashboard for monitoring and control

### Phase 3: Intelligence Layer (Future)
- Historical pattern analysis for predictive failures
- Weather integration for smart scheduling
- Plant risk assessment and recommendations
- Automated response protocols

### Phase 4: Production System (Future)
- 24/7 monitoring service
- Cloud deployment
- Multi-controller support
- Advanced reporting and analytics

## 📊 Current Capabilities

### Data Collection
- **Schedule Monitoring**: Extracts complete daily irrigation schedules
- **Actual Run Tracking**: Monitors completed irrigation cycles with water usage
- **Multi-Source Integration**: Combines web portal data with downloadable reports

### Failure Detection
- **Missing Runs**: Detects zones that should have run but didn't
- **Failed Runs**: Identifies zones that started but failed to complete
- **Water Deficit Analysis**: Calculates expected vs actual water delivery
- **Severity Classification**: CRITICAL, WARNING, INFO levels based on plant risk

### Zone Intelligence
- **Priority Classification**: HIGH, MEDIUM, LOW priority zones
- **Plant Risk Assessment**: Maximum hours without water by zone type
- **Water Usage Tracking**: Actual gallons delivered per run
- **Status Monitoring**: Normal cycles, sensor aborts, weather delays

## 🔧 Installation

### Prerequisites
- Python 3.8+
- Chrome browser (for web scraping)
- Hydrawise account credentials

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/LaurenceW01/Hydrawise.git
   cd Hydrawise
   ```

2. Create virtual environment:
   ```bash
   python -m venv hydrawise-venv
   source hydrawise-venv/Scripts/activate  # Windows
   # or
   source hydrawise-venv/bin/activate      # Linux/Mac
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials:
   # HYDRAWISE_USER=your_email
   # HYDRAWISE_PASSWORD=your_password
   # HUNTER_HYDRAWISE_API_KEY=your_api_key
   ```

5. Initialize database:
   ```bash
   python -c "from database.database_manager import DatabaseManager; db = DatabaseManager(); db.create_tables(); print('Database initialized')"
   ```

## 🚀 Usage

### Basic Monitoring
```bash
# Collect today's schedule and actual runs
python current_day_monitor.py

# Test 24-hour schedule collection
python test_24_hour_schedule.py

# Run complete data collection test
python test_current_day_complete.py
```

### Web Scraping
```bash
# Test web scraper functionality
python tests/test_web_scraper.py

# Manual schedule extraction
python -c "
from hydrawise_web_scraper import HydrawiseWebScraper
import os
from dotenv import load_dotenv
load_dotenv()
scraper = HydrawiseWebScraper(os.getenv('HYDRAWISE_USER'), os.getenv('HYDRAWISE_PASSWORD'))
scraper.start_browser()
scraper.login()
scraper.navigate_to_reports()
runs = scraper.extract_scheduled_runs()
print(f'Collected {len(runs)} scheduled runs')
scraper.stop_browser()
"
```

### Failure Detection
```bash
# Run failure detection analysis
python irrigation_failure_detector.py

# Test API monitoring
python tests/test_irrigation_monitor.py
```

## 📁 Project Structure

```
Hydrawise/
├── hydrawise_web_scraper.py      # Core web scraping functionality
├── irrigation_failure_detector.py # Failure detection and alerts
├── irrigation_monitor.py          # API-based monitoring
├── current_day_monitor.py         # Current day focused monitoring
├── config/
│   ├── web_scraper_config.py     # Web scraper selectors
│   ├── failure_detection_rules.py # Failure detection rules
│   └── failure_analysis.py       # Excel report analysis
├── database/
│   ├── schema.sql                # Database schema
│   └── database_manager.py       # Database operations
├── tests/                        # Test scripts
├── docs/                         # Documentation
└── requirements.txt              # Python dependencies
```

## 🛠️ Core Components

### HydrawiseWebScraper
- **Authentication**: Automated login to Hydrawise portal
- **Navigation**: Robust navigation to reports and data views
- **Data Extraction**: Schedule and actual run data with hover popup parsing
- **Error Handling**: Comprehensive error handling and logging

### DatabaseManager
- **Schema Management**: SQLite database with proper relationships
- **CRUD Operations**: Insert/update/query operations for all data types
- **Data Integrity**: Ensures data consistency and prevents duplicates

### FailureDetector
- **Rule Engine**: Configurable rules for different failure types
- **Alert Generation**: Creates actionable alerts with severity levels
- **Plant Risk Assessment**: Calculates time-sensitive plant risk factors

## 📊 Sample Output

```bash
📊 TESTING TODAY'S ACTUAL RUNS...
✅ Actual runs collected: 18
   Sample: Rear Left Pots, Baskets & Planters (M) at 06:00AM for 1min
           Water used: 7.5 gallons
           Front Planters & Pots at 06:29PM for 1min

📈 SUMMARY:
   Scheduled for today: 22 runs
   Completed so far: 18 runs
   Total water delivered: 180.0 gallons
   Runs with water data: 14/18

✅ SUCCESS: Both scheduled and actual data collection working!
   Core monitoring capability: OPERATIONAL
```

## 🔮 Next Development Phases

### Immediate Priorities
1. **Manual Emergency Response**: Complete API-based manual zone control
2. **Real-time Alerts**: Email/SMS notification system
3. **Tomorrow's Schedule**: Fix date navigation for 24-hour monitoring
4. **Historical Analysis**: Excel report integration for failure patterns

### Medium Term
1. **Dashboard Interface**: Web-based monitoring and control dashboard
2. **Weather Integration**: Smart scheduling based on weather conditions
3. **Predictive Analytics**: Machine learning for failure prediction
4. **Mobile App**: iOS/Android app for remote monitoring

## 🤝 Contributing

This is a personal irrigation monitoring project. For questions or suggestions, please open an issue.

## 📄 License

Private repository - All rights reserved.

## 🔍 Troubleshooting

### Common Issues
1. **Login Failed**: Check HYDRAWISE_USER and HYDRAWISE_PASSWORD in .env
2. **Chrome Driver Issues**: Ensure Chrome browser is installed and updated
3. **No Schedule Data**: Verify you're logged into the correct Hydrawise account
4. **Database Errors**: Run database initialization script

### Debug Mode
Enable detailed logging by setting headless=False in web scraper:
```python
scraper = HydrawiseWebScraper(username, password, headless=False)
```

---

**Last Updated**: August 2025  
**System Status**: Core irrigation failure detection system operational  
**Next Milestone**: 24-hour schedule monitoring and manual zone control
