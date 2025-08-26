#!/usr/bin/env python3
"""
Test StopAll Command

Quick test to see if the stopall command actually works,
since that was successful in our diagnostics.
"""

import os
from dotenv import load_dotenv
from hydrawise_api_explorer import HydrawiseAPIExplorer


def test_stopall():
    """Test if stopall command actually works."""
    load_dotenv()
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    explorer = HydrawiseAPIExplorer(api_key, respect_rate_limits=True, aggressive_rate_limiting=False)
    
    print("[SYMBOL] TESTING STOPALL COMMAND")
    print("=" * 30)
    
    try:
        result = explorer.stop_all_zones()
        print(f"[SYMBOL] StopAll Result: {result}")
        
        if result.get('message_type') == 'info':
            print(f"[SYMBOL] StopAll command successful: {result.get('message')}")
        else:
            print(f"[SYMBOL] StopAll command failed: {result}")
    
    except Exception as e:
        print(f"[SYMBOL] StopAll command error: {e}")


if __name__ == "__main__":
    test_stopall()

