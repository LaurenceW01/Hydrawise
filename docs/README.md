# Hunter Hydrawise API Explorer

A comprehensive Python tool for exploring and controlling Hunter Hydrawise irrigation systems through their REST API.

## Features

### 🔍 API Exploration
- Comprehensive endpoint discovery
- Automatic data analysis and formatting
- Raw response inspection for debugging

### 🎛️ Zone Control
- **Start zones** for custom durations
- **Stop individual zones** immediately
- **Stop all zones** at once
- **Suspend zones** for specified days
- **Resume suspended zones**

### 📊 Data Analysis
- Controller information and status
- Zone details and current state
- Watering schedules and history
- Flow meter data detection (if available)

### 💧 Water Usage Monitoring
- Attempts to discover flow meter endpoints
- Analyzes responses for water usage data
- Compatible with Hunter HC Flow Meter systems

### 🚦 Rate Limiting & API Compliance
- **Automatic rate limiting** following Hydrawise's official limits:
  - General API calls: 30 per 5 minutes
  - Zone control operations: 3 per 30 seconds
- **nextpoll respect** - honors API polling recommendations
- **429 error handling** with automatic retry
- **Real-time status tracking** of API usage
- **Safe testing mode** with rate limit reset option

## Quick Start

### 1. Get Your API Key
1. Sign in to your Hydrawise account
2. Click the Menu icon
3. Select "Account Details"
4. Choose "Generate API Key"

### 2. Set Up Environment
```bash
# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp env.example .env

# Edit .env and add your API key:
# HUNTER_HYDRAWISE_API_KEY=your_actual_api_key_here
```

### 3. Quick Test
```bash
# Test your setup quickly
python quick_start.py
```

### 4. Full Exploration
```bash
# Run the comprehensive explorer
python hydrawise_api_explorer.py
```

## Usage Examples

### Basic Exploration
Run option 1 for a comprehensive exploration that will:
- Retrieve all controller and zone information
- Analyze current status and schedules
- Attempt to discover flow meter data
- Display formatted results

### Zone Control Examples

**Start a zone for 15 minutes:**
- Select option 4
- Enter zone ID (e.g., 123456)
- Enter duration: 15

**Stop a specific zone:**
- Select option 5
- Enter zone ID to stop

**Emergency stop all zones:**
- Select option 6

**Suspend a zone for 3 days:**
- Select option 7
- Enter zone ID
- Enter days: 3

## API Endpoints Explored

The tool automatically tests these Hydrawise API endpoints:

### Core Endpoints
- `GET /api/v1/customerdetails` - Controller and zone information
- `GET /api/v1/statusschedule` - Current status and schedules
- `GET /api/v1/setzone` - Zone control commands

### Attempted Flow Meter Endpoints
- `GET /api/v1/flowmeter` - Direct flow meter data
- `GET /api/v1/waterusage` - Water usage reports
- `GET /api/v1/reports` - General reporting data
- `GET /api/v1/sensordata` - Sensor information
- `GET /api/v1/measurements` - Measurement data

## Zone Control Commands

### Start Zone
```python
explorer.start_zone(zone_id=123456, duration_minutes=15)
```

### Stop Zone
```python
explorer.stop_zone(zone_id=123456)
```

### Stop All Zones
```python
explorer.stop_all_zones()
```

### Suspend Zone
```python
explorer.suspend_zone(zone_id=123456, days=3)
```

### Resume Zone
```python
explorer.resume_zone(zone_id=123456)
```

## Flow Meter Integration

This tool is designed to work with Hunter HC Flow Meters connected to Hydrawise controllers. While flow meter data access through the REST API is not fully documented, the tool:

1. **Searches multiple potential endpoints** for flow data
2. **Analyzes zone responses** for embedded water usage information
3. **Reports findings** in both structured and raw format

### Expected Flow Data Fields
The tool looks for these fields in API responses:
- `flow` - Current flow rate
- `water_used` - Total water used
- `flow_rate` - Flow rate measurements
- `usage` - General usage data
- `gallons` / `liters` - Volume measurements

## Troubleshooting

### Common Issues

**"API request failed" errors:**
- Verify your API key is correct
- Check your internet connection
- Ensure the Hydrawise service is operational

**"No zone data found" messages:**
- Your API key may not have the required permissions
- Controller may be offline
- Account may not have any configured zones

**Flow meter data not appearing:**
- Flow meter may not be properly configured in Hydrawise
- Data might only be available through GraphQL API
- Contact Hydrawise support for flow data API access

### Getting Help

1. **Check the raw API responses** displayed during comprehensive exploration
2. **Verify your Hydrawise setup** through the web/mobile app
3. **Contact Hydrawise support** for API-specific issues
4. **Check Hunter Industries documentation** for the latest API updates

## Safety Notes

⚠️ **Important Safety Considerations:**

- **Test in safe conditions**: Don't test zone control during extreme weather
- **Monitor water usage**: Be aware of water restrictions in your area
- **Emergency stops**: Know how to manually override your system
- **Controller access**: Ensure you have physical access to your controller

## Additional Tools

### Rate Limiting Demo
Test and understand the rate limiting behavior:
```bash
python hydrawise_rate_limit_demo.py
```

### Zone Control Examples
Advanced zone control scenarios:
```bash
python hydrawise_zone_control_examples.py
```

## Rate Limiting Details

This tool automatically respects Hydrawise's API limits:

### Official Limits
- **General API calls**: 30 requests per 5-minute window
- **Zone control operations**: 3 requests per 30-second window
- **nextpoll recommendations**: Automatic respect for API polling guidance

### Safety Features
- ⏳ **Automatic delays** when approaching limits
- 🚦 **Real-time monitoring** of quota usage
- 🔄 **Retry logic** for 429 rate limit responses
- 📊 **Status tracking** with detailed timing information

### Best Practices
1. **Use `quick_start.py`** for initial testing
2. **Monitor rate limit status** regularly during development
3. **Respect nextpoll** recommendations in the API responses
4. **Batch operations** when possible to reduce API calls
5. **Test with rate limiting enabled** (default behavior)

## Advanced Usage

### Custom API Calls
The `HydrawiseAPIExplorer` class can be imported and used in your own scripts:

```python
from hydrawise_api_explorer import HydrawiseAPIExplorer

# Initialize with rate limiting (recommended)
explorer = HydrawiseAPIExplorer("your_api_key_here", respect_rate_limits=True)

# Get customer details
data = explorer.get_customer_details()

# Check rate limit status
status = explorer.get_rate_limit_status()
print(f"API calls used: {status['general_calls_used']}/{status['general_calls_limit']}")

# Zone control (automatically rate limited)
explorer.start_zone(zone_id=123456, duration_minutes=10)
```

### Disable Rate Limiting (Not Recommended)
```python
# Only for testing - may get you blocked by Hydrawise
explorer = HydrawiseAPIExplorer("your_api_key_here", respect_rate_limits=False)
```

### Automated Scheduling
You can use this tool as a foundation for automated irrigation scheduling based on:
- Weather data integration
- Soil moisture sensors
- Custom watering algorithms
- Flow meter readings (if available)

## License

This tool is provided as-is for educational and personal use. Please respect Hydrawise's API terms of service and rate limits.

## Contributing

Found issues or want to add features? This tool was created to help explore the Hydrawise API capabilities. Feel free to extend it for your specific needs.
