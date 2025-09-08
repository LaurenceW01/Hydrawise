#!/usr/bin/env python3
"""
Restart NSSM Service with Enhanced Logging

This script restarts the NSSM service to apply the enhanced logging changes
that will show when the next scheduled collections will run.

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
    print("Hydrawise NSSM Service Restart with Enhanced Logging")
    print("=" * 55)
    print()
    
    print("1. Stopping NSSM service...")
    if not run_command("nssm stop hydrawisecollector"):
        print("[ERROR] Failed to stop service")
        return 1
    
    print("\n2. Waiting 3 seconds...")
    time.sleep(3)
    
    print("3. Starting NSSM service...")
    if not run_command("nssm start hydrawisecollector"):
        print("[ERROR] Failed to start service")
        return 1
    
    print("\n4. Checking service status...")
    run_command("nssm status hydrawisecollector")
    
    print("\n[OK] Service restarted successfully!")
    print("\nThe enhanced logging will now show:")
    print("- [SCHEDULE] messages showing next collection times")
    print("- [STATUS] periodic updates every 15 minutes")
    print("- Clear timestamps for when collections are scheduled")
    print("\nMonitor the logs with:")
    print("   tail -f logs\\nssm_stdout.log")
    print("\nYou should see messages like:")
    print("   [SCHEDULE] Next interval collection scheduled for: 09/08/2025 09:35:00 AM CDT")
    print("   [STATUS] Next interval collection: 09/08/2025 09:35:00 AM CDT")
    
    return 0

if __name__ == "__main__":
    exit(main())
