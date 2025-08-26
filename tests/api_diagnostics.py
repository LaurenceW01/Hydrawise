#!/usr/bin/env python3
"""
Hydrawise API Diagnostics

This script tests the API connection stability and identifies issues
with the statusschedule endpoint that were causing failures.

Author: AI Assistant
Date: 2024
"""

import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv


def test_api_endpoints():
    """Test different API endpoints to identify issues."""
    load_dotenv()
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        print("[SYMBOL] No API key found")
        return
    
    print("[SYMBOL] HYDRAWISE API DIAGNOSTICS")
    print("=" * 40)
    print(f"[SYMBOL] API key loaded: {api_key[:8]}..." + "*" * (len(api_key) - 8))
    print(f"[SYMBOL] Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    base_url = "https://api.hydrawise.com/api/v1"
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'HydrawiseAPIDiagnostics/1.0',
        'Accept': 'application/json'
    })
    
    endpoints_to_test = [
        ('customerdetails', 'Customer Details'),
        ('statusschedule', 'Status Schedule'),
        ('setzone', 'Zone Control (GET only for test)')
    ]
    
    results = {}
    
    for endpoint, description in endpoints_to_test:
        print(f"\n[SYMBOL] Testing {description}")
        print("-" * 30)
        
        # Test both .php and non-.php versions
        urls_to_test = [
            f"{base_url}/{endpoint}.php",
            f"{base_url}/{endpoint}"
        ]
        
        for url in urls_to_test:
            print(f"[SYMBOL] Testing: {url}")
            
            params = {'api_key': api_key}
            
            try:
                start_time = time.time()
                response = session.get(url, params=params, timeout=30)
                elapsed = time.time() - start_time
                
                print(f"   [SYMBOL][SYMBOL] Response time: {elapsed:.2f}s")
                print(f"   [SYMBOL] Status code: {response.status_code}")
                print(f"   [SYMBOL] Content length: {len(response.content)} bytes")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"   [SYMBOL] JSON valid - Keys: {list(data.keys())}")
                        
                        # Check for specific data
                        if 'relays' in data:
                            print(f"   [SYMBOL] Found {len(data['relays'])} zones")
                        if 'sensors' in data:
                            print(f"   [SYMBOL] Found {len(data['sensors'])} sensors")
                        if 'nextpoll' in data:
                            print(f"   [SYMBOL] Next poll recommended: {data['nextpoll']}s")
                        
                        results[url] = {
                            'status': 'success',
                            'response_time': elapsed,
                            'data_keys': list(data.keys())
                        }
                        
                    except ValueError as e:
                        print(f"   [SYMBOL] Invalid JSON: {e}")
                        print(f"   [SYMBOL] Raw content: {response.text[:200]}...")
                        results[url] = {'status': 'invalid_json', 'error': str(e)}
                        
                else:
                    print(f"   [SYMBOL] HTTP Error: {response.status_code}")
                    print(f"   [SYMBOL] Response: {response.text[:200]}")
                    results[url] = {
                        'status': 'http_error',
                        'status_code': response.status_code,
                        'response': response.text[:200]
                    }
                
            except requests.exceptions.Timeout as e:
                print(f"   [SYMBOL] Timeout after 30s: {e}")
                results[url] = {'status': 'timeout', 'error': str(e)}
                
            except requests.exceptions.ConnectionError as e:
                print(f"   [SYMBOL] Connection error: {e}")
                results[url] = {'status': 'connection_error', 'error': str(e)}
                
            except Exception as e:
                print(f"   [SYMBOL] Unexpected error: {e}")
                results[url] = {'status': 'unexpected_error', 'error': str(e)}
            
            # Small delay between tests
            time.sleep(2)
    
    # Summary
    print(f"\n[SYMBOL] DIAGNOSTIC SUMMARY")
    print("=" * 40)
    
    working_endpoints = []
    failing_endpoints = []
    
    for url, result in results.items():
        if result.get('status') == 'success':
            working_endpoints.append(url)
            print(f"[SYMBOL] {url} - Working ({result.get('response_time', 0):.2f}s)")
        else:
            failing_endpoints.append(url)
            print(f"[SYMBOL] {url} - {result.get('status', 'unknown')} - {result.get('error', 'No details')}")
    
    print(f"\n[SYMBOL] RECOMMENDATIONS")
    print("-" * 20)
    
    if working_endpoints:
        print(f"[SYMBOL] Use these working endpoints:")
        for url in working_endpoints:
            print(f"   - {url}")
    
    if failing_endpoints:
        print(f"[SYMBOL][SYMBOL] Avoid these failing endpoints:")
        for url in failing_endpoints:
            print(f"   - {url}")
    
    # Specific recommendations based on patterns
    php_working = any('.php' in url for url in working_endpoints)
    non_php_working = any('.php' not in url for url in working_endpoints)
    
    if php_working and not non_php_working:
        print("\n[SYMBOL] Use .php endpoints exclusively")
    elif non_php_working and not php_working:
        print("\n[SYMBOL] Use non-.php endpoints exclusively") 
    elif php_working and non_php_working:
        print("\n[SYMBOL] Both formats work - prefer .php for consistency")
    else:
        print("\n[SYMBOL] No working endpoints found - check API key and network")


def test_connection_stability():
    """Test connection stability with multiple rapid requests."""
    load_dotenv()
    api_key = os.getenv('HUNTER_HYDRAWISE_API_KEY')
    
    if not api_key:
        print("[SYMBOL] No API key found")
        return
    
    print(f"\n[SYMBOL] CONNECTION STABILITY TEST")
    print("=" * 40)
    print("Making 5 rapid requests to test for connection issues...")
    
    url = "https://api.hydrawise.com/api/v1/customerdetails.php"
    session = requests.Session()
    params = {'api_key': api_key}
    
    successes = 0
    failures = []
    
    for i in range(5):
        print(f"\nRequest {i+1}/5:")
        try:
            start_time = time.time()
            response = session.get(url, params=params, timeout=30)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                print(f"   [SYMBOL] Success ({elapsed:.2f}s)")
                successes += 1
            else:
                print(f"   [SYMBOL] HTTP {response.status_code}")
                failures.append(f"HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   [SYMBOL] Error: {e}")
            failures.append(str(e))
        
        # Small delay between requests
        time.sleep(3)
    
    print(f"\n[SYMBOL] STABILITY RESULTS")
    print(f"[SYMBOL] Successes: {successes}/5")
    print(f"[SYMBOL] Failures: {len(failures)}/5")
    
    if failures:
        print("Failure details:")
        for i, failure in enumerate(failures, 1):
            print(f"   {i}. {failure}")


if __name__ == "__main__":
    test_api_endpoints()
    test_connection_stability()





