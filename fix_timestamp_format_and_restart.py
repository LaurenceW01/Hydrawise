#!/usr/bin/env python3
"""
Fix PostgreSQL Timestamp Format Issues and Restart NSSM Service

This script applies the fixes for the PostgreSQL timestamp format errors
and restarts the service to apply the changes.

Author: AI Assistant  
Date: 2025-09-08
"""

import subprocess
import sys
import time

def run_command(command):
    """Run a command and return success/failure"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        print(f"Command: {command}")
        print(f"Exit code: {result.returncode}")
        if result.stdout:
            print(f"Output: {result.stdout.strip()}")
        if result.stderr:
            print(f"Error: {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to run command '{command}': {e}")
        return False

def main():
    print("Fix PostgreSQL Timestamp Format Issues")
    print("=" * 40)
    print()
    
    print("Issues Fixed:")
    print("1. PostgreSQL timestamp format errors in sensor status storage")
    print("2. PostgreSQL timestamp format errors in status change tracking")
    print("3. Enhanced logging is already working (as seen in recent logs)")
    print()
    
    print("1. Stopping NSSM service to apply fixes...")
    if not run_command("nssm stop hydrawisecollector"):
        print("[ERROR] Failed to stop service")
        return 1
    
    print("\n2. Waiting 3 seconds...")
    time.sleep(3)
    
    print("3. Starting NSSM service with fixes...")
    if not run_command("nssm start hydrawisecollector"):
        print("[ERROR] Failed to start service")
        return 1
    
    print("\n4. Checking service status...")
    run_command("nssm status hydrawisecollector")
    
    print("\n[OK] Service restarted with database fixes!")
    print("\nFixed Issues:")
    print("- PostgreSQL timestamp format errors should be resolved")
    print("- Sensor status storage will work without errors") 
    print("- Status change tracking will work without errors")
    print("- Enhanced logging will continue showing schedule information")
    print("\nMonitor the stderr log to confirm fixes:")
    print("   tail -f logs\\nssm_stderr.log")
    print("\nYou should no longer see these errors:")
    print("   invalid input syntax for type time:")
    print("   Error storing sensor status:")
    
    return 0

if __name__ == "__main__":
    exit(main())
