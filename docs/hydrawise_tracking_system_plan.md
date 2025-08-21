# Hydrawise Irrigation Failure Alert System - Master Plan

## 🎯 Project Goal
Build an **irrigation failure alert system** that detects when zones are not running or planned not to run due to controller schedule changes, immediately alerting the user to take action to ensure plants receive necessary watering through manual zone control via API.

## 📋 Project Phases Overview

### **Phase 1: Alert Foundation (Real-time Monitoring)**
*Goal: Build real-time schedule monitoring to detect irrigation failures*

### **Phase 2: Emergency Response (API Integration)**
*Goal: Integrate manual zone control for immediate response to alerts*

### **Phase 3: Intelligence Layer (Pattern Detection)**
*Goal: Learn patterns and predict potential failures before they occur*

### **Phase 4: Production System (Automated Plant Protection)**
*Goal: Fully automated monitoring with intelligent alerts and response options*

---

## 🚀 Detailed Implementation Plan

### **Phase 1: Foundation - Web Scraping Core**

#### **1.1 Research & Setup**
- **Research** Hydrawise portal structure, DOM elements, authentication flow
- **Setup** Python environment with Selenium, BeautifulSoup, ChromeDriver
- **Test** basic portal access and navigation

#### **1.2 Authentication Module**
- **Build** secure login system using stored credentials
- **Handle** session management and cookie persistence
- **Implement** error handling for login failures

#### **1.3 Navigation Module**
- **Create** date navigation (previous/next day functionality)
- **Build** tab switching (Schedule ↔ Reported views)
- **Implement** robust waiting/loading detection

#### **1.4 Data Extraction Modules**
- **Schedule Scraper**: Extract planned zone runs from timeline WITH hover popup data for scheduled durations
- **Actual Scraper**: Extract reported runs + hover popup usage data
- **Data Validation**: Cross-check extracted data for completeness

### **Phase 2: Data Integration - Excel + Database**

#### **2.1 Database Design**
- **Schema**: Tables for schedules, actuals, variances, operational notes
- **Relationships**: Link zones, dates, runs, and flow measurements
- **Indexing**: Optimize for date/zone queries

#### **2.2 Excel Integration**
- **Parser**: Extract data from both Excel report types
- **Historical Import**: Bulk load months of historical data
- **Notes Integration**: Incorporate operational context from Excel

#### **2.3 Data Storage System**
- **ETL Pipeline**: Extract, Transform, Load from multiple sources
- **Data Validation**: Ensure consistency across sources
- **Conflict Resolution**: Handle discrepancies between sources

### **Phase 3: Analysis Engine - Intelligence Layer**

#### **3.1 Flow Rate Integration**
- **Import** your actual flow rate measurements (from the flow rate table)
- **Calculate** expected water usage (flow rate × scheduled duration)
- **Compare** with actual usage from hover popup data

#### **3.2 Variance Analysis**
- **Water Delivery Variance**: Scheduled vs actual gallons per zone
- **Duration Variance**: Planned vs actual run times
- **Pattern Detection**: Identify consistently over/under performing zones

#### **3.3 Reporting System**
- **Daily Reports**: Same-day scheduled vs actual comparison
- **Weekly Summaries**: Pattern analysis and trend identification  
- **Monthly Analysis**: System efficiency and optimization opportunities
- **Alert System**: Flag significant variances requiring attention

### **Phase 4: Automation & Production - Operational System**

#### **4.1 Automation Scripts**
- **Daily Collection**: Automated scraping of current day data
- **Historical Backfill**: Systematic collection of missing historical data
- **Excel Processing**: Automated download and processing of reports

#### **4.2 Production Features**
- **Real-time Monitoring**: Track current day as it unfolds
- **API Integration**: Complement web data with existing API capabilities
- **Error Recovery**: Robust handling of network/site issues
- **Logging**: Comprehensive audit trail of all operations

---

## 🛠 Technical Architecture

### **Core Components**
```
┌─ Web Scraper ────────────────┐
│  ├─ Authentication           │
│  ├─ Navigation               │
│  ├─ Schedule Extraction      │
│  └─ Actual Data Extraction   │
└──────────────────────────────┘
           │
┌─ Data Integration ───────────┐
│  ├─ Excel Parser             │
│  ├─ Database Manager         │
│  ├─ ETL Pipeline             │
│  └─ Data Validation          │
└──────────────────────────────┘
           │
┌─ Analysis Engine ────────────┐
│  ├─ Variance Calculator      │
│  ├─ Pattern Detector         │
│  ├─ Report Generator         │
│  └─ Alert System             │
└──────────────────────────────┘
           │
┌─ Production System ──────────┐
│  ├─ Automation Scheduler     │
│  ├─ Error Recovery           │
│  ├─ Monitoring Dashboard     │
│  └─ API Integration          │
└──────────────────────────────┘
```

### **Data Flow**
1. **Collection**: Web scraper + Excel downloads → Raw data
2. **Processing**: ETL pipeline → Structured database
3. **Analysis**: Variance engine → Insights and reports
4. **Action**: Alerts and recommendations → Operational decisions

---

## 🎯 Enhanced Data Collection Strategy

### **Web Portal Hover Popup Data Available**

#### **Schedule Page Hover Popups**:
- ✅ **Scheduled run time/duration** for each zone
- ✅ **Expected water usage** calculations
- ✅ **Zone identification** and timing details

#### **Reported Page Hover Popups**:
- ✅ **Actual water usage** (e.g., 7.50005587238888 Gallons)
- ✅ **Actual duration** information
- ✅ **Current readings** (e.g., 190mA)
- ✅ **Operational status** details

### **Complete Data Capture Strategy**
```
Schedule Page:
Timeline View → Zone blocks → Hover → Scheduled duration & expected usage
     │
     ↓
Reported Page:
Timeline View → Zone blocks → Hover → Actual duration & actual usage
     │
     ↓
Database:
Full comparison of scheduled vs actual for variance analysis
```

---

## 📊 Expected Outcomes

### **Immediate Benefits (Phase 1-2)**
- Complete daily schedule visibility (vs API's "next run only")
- Historical data analysis (months of operational history)
- Scheduled vs actual comparison capability with precise duration and usage data

### **Advanced Benefits (Phase 3-4)**
- Water usage variance tracking with your actual flow rates
- Operational efficiency insights and optimization opportunities
- Automated daily monitoring with minimal manual intervention
- Pattern detection for predictive maintenance and scheduling

---

## 🎯 Success Metrics

### **Technical Metrics**
- ✅ **Data Completeness**: 100% daily schedule capture vs 1 entry from API
- ✅ **Historical Coverage**: Months of data vs real-time only
- ✅ **Accuracy**: Cross-validated data from multiple sources
- ✅ **Precision**: Hover popup data for exact scheduled and actual values

### **Business Metrics**
- ✅ **Water Efficiency**: Track actual vs planned water usage
- ✅ **System Reliability**: Identify zones with consistent variances
- ✅ **Operational Insights**: Understand why zones over/under perform

---

## 🚦 Implementation Roadmap

### **Phase 1: Foundation (Weeks 1-2)**
1. Research web portal structure and hover popup mechanisms
2. Set up Selenium environment with hover event handling
3. Build authentication and navigation modules
4. Create dual scraper (Schedule + Reported pages with hover data)

### **Phase 2: Data Integration (Week 3)**
5. Design database schema for scheduled vs actual tracking
6. Build Excel parser for historical data import
7. Create ETL pipeline for multi-source data integration

### **Phase 3: Analysis Engine (Week 4)**
8. Integrate your flow rate measurements
9. Build variance analysis engine
10. Create reporting and alerting system

### **Phase 4: Production (Week 5)**
11. Automate daily data collection
12. Build monitoring dashboard
13. Test end-to-end system with real data

---

## 📝 Key Technical Notes

### **Hover Popup Handling**
- Use Selenium's `ActionChains` for mouse hover events
- Implement wait conditions for popup appearance
- Extract popup content using CSS selectors or XPath
- Handle popup disappearance timing

### **Data Validation**
- Cross-reference web data with Excel downloads
- Validate scheduled vs actual data consistency
- Flag missing or inconsistent entries
- Maintain audit trail of all data sources

### **Performance Considerations**
- Implement delays between hover events to avoid rate limiting
- Cache authentication sessions to minimize login frequency
- Batch process multiple dates efficiently
- Store incremental updates to avoid full re-scraping

---

## 🔧 Technology Stack

- **Web Scraping**: Selenium WebDriver, BeautifulSoup
- **Excel Processing**: pandas, openpyxl
- **Database**: SQLite (development) / PostgreSQL (production)
- **Analysis**: pandas, numpy, matplotlib
- **Automation**: schedule, cron (Linux/Mac) or Task Scheduler (Windows)
- **Logging**: Python logging module with rotating file handlers

---

## 💡 Next Steps

**Ready to begin Phase 1.1 - Research & Setup?**

The first step will be to examine the Hydrawise portal structure, understand the hover popup mechanisms, and set up the basic Selenium environment for reliable data extraction.
