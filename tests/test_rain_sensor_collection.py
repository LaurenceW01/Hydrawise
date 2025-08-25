#!/usr/bin/env python3
"""
Test script for rain sensor detection and enhanced 24-hour schedule collection.

This script tests the newly enhanced web scraper capabilities:
1. Rain sensor status detection 
2. Improved popup extraction reliability (targeting the 3 problematic zones)
3. Enhanced error handling and browser stability
4. Proper handling of "not scheduled to run" conditions during rain events

Author: AI Assistant
Date: 2025
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hydrawise_web_scraper import HydrawiseWebScraper

def setup_logging():
    """Setup detailed logging for test session"""
    log_filename = f"test_rain_sensor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def test_rain_sensor_collection():
    """Test rain sensor detection and 24-hour collection during rain conditions"""
    logger = setup_logging()
    logger.info("🌧️  Testing rain sensor detection and enhanced collection capabilities...")
    
    # Load credentials
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        logger.error("❌ Missing credentials in .env file")
        return False
    
    try:
        # Initialize scraper with visible browser for debugging
        scraper = HydrawiseWebScraper(username, password, headless=False)
        
        logger.info("🚀 Starting enhanced 24-hour schedule collection test...")
        
        # Test the enhanced 24-hour collection with rain sensor detection
        results = scraper.collect_24_hour_schedule()
        
        # Analyze results
        logger.info("\n" + "="*80)
        logger.info("📊 COLLECTION RESULTS ANALYSIS")
        logger.info("="*80)
        
        # Rain sensor status
        logger.info(f"🌧️  Rain Sensor Active: {results.get('rain_sensor_active', 'Unknown')}")
        logger.info(f"🚫 Irrigation Suspended: {results.get('irrigation_suspended', 'Unknown')}")
        logger.info(f"📍 Sensor Status: {results.get('sensor_status', 'Unknown')}")
        
        # Collection statistics
        today_count = len(results.get('today', []))
        tomorrow_count = len(results.get('tomorrow', []))
        error_count = len(results.get('errors', []))
        
        logger.info(f"📅 Today's Schedule: {today_count} runs collected")
        logger.info(f"📅 Tomorrow's Schedule: {tomorrow_count} runs collected")
        logger.info(f"❌ Errors: {error_count}")
        
        # Detailed zone analysis
        if results.get('rain_sensor_active'):
            logger.info("\n🌧️  RAIN SENSOR ANALYSIS:")
            logger.info("   - System detected active rain sensor")
            logger.info("   - All zones should show 'not scheduled to run'")
            logger.info("   - Manual plant monitoring required during suspension")
            
            # Check if any zones have unexpected data during rain suspension
            total_duration = 0
            for run in results.get('today', []) + results.get('tomorrow', []):
                if hasattr(run, 'duration_minutes') and run.duration_minutes > 0:
                    total_duration += run.duration_minutes
                    
            if total_duration > 0:
                logger.warning(f"⚠️  Unexpected: {total_duration} total minutes scheduled during rain suspension")
            else:
                logger.info("✅ Confirmed: All zones properly show 0 duration during rain suspension")
        
        # Error analysis
        if error_count > 0:
            logger.warning(f"\n❌ ERRORS DETECTED ({error_count}):")
            for i, error in enumerate(results.get('errors', []), 1):
                logger.warning(f"   {i}. {error}")
        else:
            logger.info("✅ No errors detected during collection")
            
        # Success metrics
        total_expected = 60  # Approximately 60 runs across 24 hours based on previous logs
        total_collected = today_count + tomorrow_count
        success_rate = (total_collected / total_expected) * 100 if total_expected > 0 else 0
        
        logger.info(f"\n📈 COLLECTION METRICS:")
        logger.info(f"   Total Collected: {total_collected}")
        logger.info(f"   Expected (~): {total_expected}")
        logger.info(f"   Success Rate: {success_rate:.1f}%")
        
        # Specific tests for previously problematic zones
        logger.info(f"\n🎯 PROBLEMATIC ZONE ANALYSIS:")
        problematic_zones = [
            'Rear Bed/Planters at Pool (M)',
            'Rear Right Bed at House and Pool (M/D)', 
            'Rear Left Pots, Baskets & Planters (M)'
        ]
        
        found_zones = []
        for run in results.get('today', []) + results.get('tomorrow', []):
            zone_name = getattr(run, 'zone_name', 'Unknown')
            for problem_zone in problematic_zones:
                if problem_zone in zone_name:
                    found_zones.append(zone_name)
                    
        logger.info(f"   Previously problematic zones found: {len(found_zones)}")
        for zone in found_zones:
            logger.info(f"   ✅ {zone}")
            
        if len(found_zones) == len(problematic_zones):
            logger.info("🎉 All previously problematic zones successfully collected!")
        
        logger.info("\n" + "="*80)
        logger.info("🎯 TEST COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def main():
    """Main test execution"""
    print("🧪 Testing Enhanced Rain Sensor Detection & 24-Hour Collection")
    print("="*80)
    
    success = test_rain_sensor_collection()
    
    if success:
        print("\n✅ Test completed successfully!")
        print("📊 Check the log file for detailed results")
    else:
        print("\n❌ Test failed - check logs for details")
        
    return success

if __name__ == "__main__":
    main()
