#!/usr/bin/env python3
"""
Fix Automated Collector Startup Issue

This script helps fix the issue where the automated collector gets stuck
in "startup in progress" mode and never proceeds to interval collections.

Author: AI Assistant
Date: 2025-09-15
"""

import os
import sys
import logging
import signal
import time

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)

def kill_existing_collectors():
    """Kill any existing automated collector processes"""
    try:
        import psutil
        
        killed_count = 0
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] == 'python.exe' and proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if 'automated_collector.py' in cmdline:
                        print(f"Killing automated collector process: PID {proc.info['pid']}")
                        proc.kill()
                        killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed_count > 0:
            print(f"Killed {killed_count} automated collector process(es)")
            time.sleep(2)  # Wait for processes to fully terminate
        else:
            print("No automated collector processes found")
            
    except ImportError:
        print("psutil not available - using taskkill command")
        os.system('taskkill /f /im python.exe /fi "WINDOWTITLE eq *automated_collector*" 2>nul')

def restart_collector_service():
    """Restart the automated collector as a Windows service"""
    try:
        print("Stopping Hydrawise service...")
        os.system('sc stop "Hydrawise Automated Collector" 2>nul')
        time.sleep(3)
        
        print("Starting Hydrawise service...")
        result = os.system('sc start "Hydrawise Automated Collector" 2>nul')
        
        if result == 0:
            print("✅ Service restarted successfully")
            return True
        else:
            print("⚠️ Service restart may have failed - check service status")
            return False
            
    except Exception as e:
        print(f"❌ Error restarting service: {e}")
        return False

def start_collector_manually():
    """Start the automated collector manually in the current console"""
    try:
        print("Starting automated collector manually...")
        print("Press Ctrl+C to stop the collector")
        print("-" * 50)
        
        # Import and run the automated collector
        from automated_collector import AutomatedCollector, ScheduleConfig
        
        # Create configuration
        config = ScheduleConfig()
        
        # Create collector
        collector = AutomatedCollector(config, log_level="INFO")
        
        # Set up signal handling
        def signal_handler(signum, frame):
            print("\n[SHUTDOWN] Signal received...")
            collector.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start collector
        collector.start()
        
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Manual collector stopped")
    except Exception as e:
        print(f"❌ Error starting manual collector: {e}")

def main():
    """Main function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("Hydrawise Automated Collector Startup Fix")
    print("=" * 50)
    
    # Kill any existing processes first
    kill_existing_collectors()
    
    print("\nChoose an option:")
    print("1. Restart as Windows service (recommended)")
    print("2. Start manually in this console")
    print("3. Just kill existing processes and exit")
    
    while True:
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            success = restart_collector_service()
            if success:
                print("\n✅ Service restarted. Check logs for startup progress.")
            else:
                print("\n⚠️ Service restart failed. Try option 2 for manual start.")
            break
            
        elif choice == "2":
            start_collector_manually()
            break
            
        elif choice == "3":
            print("\n✅ Existing processes killed. You can now start the collector manually.")
            break
            
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()



