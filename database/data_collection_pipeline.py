#!/usr/bin/env python3
"""
Hydrawise Data Collection Pipeline

Orchestrates daily data collection from web scraper and stores in database
with variance analysis and failure detection.

Author: AI Assistant
Date: 2025-08-21
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our modules
from hydrawise_web_scraper_refactored import HydrawiseWebScraper
from database.intelligent_data_storage import IntelligentDataStorage
from irrigation_failure_detector import IrrigationFailureDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database/data_collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataCollectionPipeline:
    """Orchestrates complete irrigation data collection and analysis"""
    
    def __init__(self, username: str, password: str, db_path: str = "database/irrigation_data.db"):
        """Initialize pipeline with credentials and enhanced database storage"""
        self.username = username
        self.password = password
        self.db = IntelligentDataStorage(db_path)
        self.scraper = HydrawiseWebScraper(username, password, headless=True)
        self.failure_detector = IrrigationFailureDetector(username, password)
        
    def collect_daily_data(self, target_date: date = None) -> Dict[str, any]:
        """
        Complete daily data collection workflow
        
        Returns:
            Dict with collection results and analysis
        """
        if target_date is None:
            target_date = date.today()
            
        logger.info(f"Starting daily data collection for {target_date}")
        start_time = datetime.now()
        
        results = {
            'target_date': target_date,
            'start_time': start_time,
            'scheduled_runs': 0,
            'actual_runs': 0,
            'failures_detected': 0,
            'errors': 0,
            'error_details': [],
            'success': False
        }
        
        try:
            # Step 1: Collect scheduled runs
            logger.info("Collecting scheduled runs...")
            scheduled_runs = self._collect_scheduled_runs(target_date)
            results['scheduled_runs'] = len(scheduled_runs)
            
            # Step 2: Collect actual runs
            logger.info("Collecting actual runs...")
            actual_runs = self._collect_actual_runs(target_date)
            results['actual_runs'] = len(actual_runs)
            
            # Step 3: Store data in database
            logger.info("Storing data in database...")
            self._store_collected_data(scheduled_runs, actual_runs, target_date)
            
            # Step 4: Calculate variance analysis
            logger.info("Calculating variance analysis...")
            variance_results = self.db.calculate_daily_variance(target_date)
            results['variance_analysis'] = variance_results
            
            # Step 5: Run failure detection
            logger.info("Running failure detection...")
            failure_results = self._run_failure_detection(target_date)
            results['failures_detected'] = len(failure_results.get('alerts', []))
            results['failure_analysis'] = failure_results
            
            # Step 6: Update system status
            logger.info("Updating system status...")
            self._update_system_status(target_date, results)
            
            results['success'] = True
            results['end_time'] = datetime.now()
            results['duration'] = (results['end_time'] - start_time).total_seconds()
            
            logger.info(f"Data collection completed successfully: {results['scheduled_runs']} scheduled, {results['actual_runs']} actual, {results['failures_detected']} failures")
            
        except Exception as e:
            logger.error(f"Data collection failed: {e}")
            results['errors'] += 1
            results['error_details'].append(str(e))
            results['end_time'] = datetime.now()
            
        finally:
            # Log collection session
            self.db.log_collection_session(
                collection_type='daily_scrape',
                scheduled_count=results['scheduled_runs'],
                actual_count=results['actual_runs'],
                errors=results['errors'],
                details='; '.join(results['error_details']) if results['error_details'] else None
            )
            
        return results
        
    def _collect_scheduled_runs(self, target_date: date) -> List:
        """Collect scheduled runs using web scraper"""
        try:
            self.scraper.start_browser()
            if not self.scraper.login():
                raise Exception("Failed to login to Hydrawise portal")
                
            self.scraper.navigate_to_reports()
            
            # Extract scheduled runs for target date
            scheduled_runs = self.scraper.extract_scheduled_runs(
                datetime.combine(target_date, datetime.min.time())
            )
            
            logger.info(f"Collected {len(scheduled_runs)} scheduled runs")
            return scheduled_runs
            
        except Exception as e:
            logger.error(f"Failed to collect scheduled runs: {e}")
            raise
        finally:
            try:
                self.scraper.stop_browser()
            except:
                pass
                
    def _collect_actual_runs(self, target_date: date) -> List:
        """Collect actual runs using web scraper"""
        try:
            self.scraper.start_browser()
            if not self.scraper.login():
                raise Exception("Failed to login to Hydrawise portal")
                
            self.scraper.navigate_to_reports()
            
            # Extract actual runs for target date
            actual_runs = self.scraper.extract_actual_runs(
                datetime.combine(target_date, datetime.min.time())
            )
            
            logger.info(f"Collected {len(actual_runs)} actual runs")
            return actual_runs
            
        except Exception as e:
            logger.error(f"Failed to collect actual runs: {e}")
            raise
        finally:
            try:
                self.scraper.stop_browser()
            except:
                pass
                
    def _store_collected_data(self, scheduled_runs: List, actual_runs: List, target_date: date):
        """Store collected data in database with enhanced popup analysis"""
        try:
            scheduled_count = self.db.store_scheduled_runs_enhanced(scheduled_runs, target_date)
            actual_count = self.db.store_actual_runs_enhanced(actual_runs, target_date)
            
            logger.info(f"Stored {scheduled_count} scheduled and {actual_count} actual runs with full popup data")
            
        except Exception as e:
            logger.error(f"Failed to store collected data: {e}")
            raise
            
    def _run_failure_detection(self, target_date: date) -> Dict:
        """Run failure detection analysis"""
        try:
            # Use the existing failure detector
            system_status = self.failure_detector.detect_failures(
                datetime.combine(target_date, datetime.min.time())
            )
            
            return {
                'system_status': system_status.status,
                'total_zones': system_status.total_zones,
                'zones_with_failures': system_status.zones_with_failures,
                'alerts': [
                    {
                        'zone_name': alert.zone_name,
                        'severity': alert.severity,
                        'failure_type': alert.failure_type,
                        'description': alert.description,
                        'plant_risk': alert.plant_risk,
                        'water_deficit': alert.water_deficit
                    }
                    for alert in system_status.alerts
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to run failure detection: {e}")
            return {
                'system_status': 'ERROR',
                'error': str(e),
                'alerts': []
            }
            
    def _update_system_status(self, target_date: date, results: Dict):
        """Update system status table with latest results"""
        try:
            with self.db._get_connection() if hasattr(self.db, '_get_connection') else sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.cursor()
                
                # Calculate totals from results
                total_zones = len(set([r.zone_name for r in results.get('scheduled_runs', [])]))
                failure_analysis = results.get('failure_analysis', {})
                
                cursor.execute("""
                    INSERT OR REPLACE INTO system_status
                    (status_date, overall_status, total_zones, zones_with_failures,
                     critical_alerts, warning_alerts, last_schedule_scrape, last_actual_scrape)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_date,
                    failure_analysis.get('system_status', 'UNKNOWN'),
                    total_zones,
                    failure_analysis.get('zones_with_failures', 0),
                    len([a for a in failure_analysis.get('alerts', []) if a.get('severity') == 'CRITICAL']),
                    len([a for a in failure_analysis.get('alerts', []) if a.get('severity') == 'WARNING']),
                    datetime.now(),
                    datetime.now()
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update system status: {e}")
            
    def collect_historical_data(self, start_date: date, end_date: date = None) -> Dict:
        """Collect historical data for a date range"""
        if end_date is None:
            end_date = date.today()
            
        logger.info(f"Starting historical data collection from {start_date} to {end_date}")
        
        results = {
            'start_date': start_date,
            'end_date': end_date,
            'days_collected': 0,
            'total_scheduled': 0,
            'total_actual': 0,
            'errors': 0,
            'error_dates': []
        }
        
        current_date = start_date
        while current_date <= end_date:
            try:
                logger.info(f"Collecting data for {current_date}")
                daily_results = self.collect_daily_data(current_date)
                
                if daily_results['success']:
                    results['days_collected'] += 1
                    results['total_scheduled'] += daily_results['scheduled_runs']
                    results['total_actual'] += daily_results['actual_runs']
                else:
                    results['errors'] += 1
                    results['error_dates'].append(current_date)
                    
            except Exception as e:
                logger.error(f"Failed to collect data for {current_date}: {e}")
                results['errors'] += 1
                results['error_dates'].append(current_date)
                
            current_date += timedelta(days=1)
            
        logger.info(f"Historical collection completed: {results['days_collected']} days, {results['total_scheduled']} scheduled runs, {results['total_actual']} actual runs")
        return results
        
    def generate_collection_report(self, days: int = 7) -> str:
        """Generate a human-readable collection status report"""
        recent_collections = self.db.get_recent_collections(days)
        daily_summary = self.db.get_daily_summary()
        active_failures = self.db.get_active_failures()
        
        report = []
        report.append("=" * 60)
        report.append("HYDRAWISE DATA COLLECTION STATUS REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M%p')}")
        report.append("")
        
        # Recent collection summary
        report.append(f"RECENT COLLECTIONS (Last {days} days):")
        report.append("-" * 40)
        if recent_collections:
            for collection in recent_collections[:5]:  # Show last 5
                status_icon = "✅" if collection['status'] == 'SUCCESS' else "⚠️" if collection['status'] == 'PARTIAL' else "❌"
                report.append(f"{status_icon} {collection['collection_date']}: {collection['scheduled_runs_collected']} scheduled, {collection['actual_runs_collected']} actual")
        else:
            report.append("No recent collections found")
        report.append("")
        
        # Current system status
        report.append("CURRENT SYSTEM STATUS:")
        report.append("-" * 25)
        report.append(f"Total Zones: {daily_summary['total_zones']}")
        report.append(f"Zones with Issues: {daily_summary['zones_with_issues']}")
        
        failure_counts = daily_summary['failure_counts']
        if failure_counts:
            report.append(f"Critical Alerts: {failure_counts.get('CRITICAL', 0)}")
            report.append(f"Warning Alerts: {failure_counts.get('WARNING', 0)}")
        else:
            report.append("No active alerts")
        report.append("")
        
        # Active failures
        if active_failures:
            report.append("ACTIVE FAILURES REQUIRING ATTENTION:")
            report.append("-" * 40)
            for failure in active_failures[:10]:  # Show top 10
                report.append(f"❗ {failure['zone_name']}: {failure['description']}")
                report.append(f"   Severity: {failure['severity']} | Action: {failure['recommended_action']}")
                report.append("")
        else:
            report.append("✅ NO ACTIVE FAILURES - SYSTEM HEALTHY")
            report.append("")
            
        report.append("=" * 60)
        
        return "\n".join(report)
        
    def close(self):
        """Clean up resources"""
        self.db.close()
        try:
            self.scraper.stop_browser()
        except:
            pass

def main():
    """Main function for running data collection pipeline"""
    
    # Load environment variables
    load_dotenv()
    username = os.getenv('HYDRAWISE_USER')
    password = os.getenv('HYDRAWISE_PASSWORD')
    
    if not username or not password:
        print("Error: HYDRAWISE_USER and HYDRAWISE_PASSWORD must be set in .env file")
        return
        
    print("Hydrawise Data Collection Pipeline")
    print("=" * 50)
    
    # Initialize pipeline
    pipeline = DataCollectionPipeline(username, password)
    
    try:
        # Run daily collection for today
        print("Running daily data collection...")
        results = pipeline.collect_daily_data()
        
        if results['success']:
            print(f"✅ Collection successful:")
            print(f"   Scheduled runs: {results['scheduled_runs']}")
            print(f"   Actual runs: {results['actual_runs']}")
            print(f"   Failures detected: {results['failures_detected']}")
            print(f"   Duration: {results['duration']:.1f} seconds")
        else:
            print(f"❌ Collection failed: {results['error_details']}")
            
        # Generate status report
        print("\nGenerating status report...")
        report = pipeline.generate_collection_report()
        print(report)
        
        # Save report to file
        report_filename = f"database/collection_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w') as f:
            f.write(report)
        print(f"\nReport saved to: {report_filename}")
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        pipeline.close()

if __name__ == "__main__":
    main()
