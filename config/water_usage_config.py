#!/usr/bin/env python3
"""
Water Usage Configuration Module

Provides configurable thresholds for water usage variance detection.
Reads from environment variables with sensible defaults.

Author: AI Assistant
Date: 2025-01-27
"""

import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Default thresholds for water usage variance detection
DEFAULT_HIGH_WATER_USAGE = 2.0  # Usage > 2.0x expected is considered too high (double)
DEFAULT_LOW_WATER_USAGE = 0.5   # Usage < 0.5x expected is considered too low (half)


def get_water_usage_thresholds() -> Tuple[float, float]:
    """
    Get water usage variance thresholds from environment variables or defaults.
    
    Environment Variables:
        HIGH_WATER_USAGE: Multiplier for high usage threshold (default: 2.0)
        LOW_WATER_USAGE: Multiplier for low usage threshold (default: 0.5)
    
    Returns:
        Tuple of (high_usage_multiplier, low_usage_multiplier)
    """
    # Read high water usage threshold
    high_usage_str = os.getenv('HIGH_WATER_USAGE')
    if high_usage_str:
        try:
            high_usage = float(high_usage_str)
            if high_usage <= 0:
                logger.warning(f"HIGH_WATER_USAGE must be positive, got {high_usage}. Using default {DEFAULT_HIGH_WATER_USAGE}")
                high_usage = DEFAULT_HIGH_WATER_USAGE
        except ValueError:
            logger.warning(f"Invalid HIGH_WATER_USAGE value '{high_usage_str}'. Using default {DEFAULT_HIGH_WATER_USAGE}")
            high_usage = DEFAULT_HIGH_WATER_USAGE
    else:
        high_usage = DEFAULT_HIGH_WATER_USAGE
    
    # Read low water usage threshold
    low_usage_str = os.getenv('LOW_WATER_USAGE')
    if low_usage_str:
        try:
            low_usage = float(low_usage_str)
            if low_usage <= 0:
                logger.warning(f"LOW_WATER_USAGE must be positive, got {low_usage}. Using default {DEFAULT_LOW_WATER_USAGE}")
                low_usage = DEFAULT_LOW_WATER_USAGE
        except ValueError:
            logger.warning(f"Invalid LOW_WATER_USAGE value '{low_usage_str}'. Using default {DEFAULT_LOW_WATER_USAGE}")
            low_usage = DEFAULT_LOW_WATER_USAGE
    else:
        low_usage = DEFAULT_LOW_WATER_USAGE
    
    # Validate that high threshold is greater than low threshold
    if high_usage <= low_usage:
        logger.warning(f"HIGH_WATER_USAGE ({high_usage}) should be greater than LOW_WATER_USAGE ({low_usage}). "
                      f"Using defaults: high={DEFAULT_HIGH_WATER_USAGE}, low={DEFAULT_LOW_WATER_USAGE}")
        high_usage = DEFAULT_HIGH_WATER_USAGE
        low_usage = DEFAULT_LOW_WATER_USAGE
    
    logger.debug(f"Water usage thresholds: high={high_usage}x, low={low_usage}x")
    return high_usage, low_usage


def get_high_water_usage_threshold() -> float:
    """
    Get the high water usage threshold multiplier.
    
    Returns:
        Float multiplier for high usage detection
    """
    high_usage, _ = get_water_usage_thresholds()
    return high_usage


def get_low_water_usage_threshold() -> float:
    """
    Get the low water usage threshold multiplier.
    
    Returns:
        Float multiplier for low usage detection
    """
    _, low_usage = get_water_usage_thresholds()
    return low_usage


if __name__ == "__main__":
    """Test the configuration loading"""
    import sys
    
    print("Water Usage Configuration Test")
    print("=" * 40)
    
    # Test with no environment variables
    high, low = get_water_usage_thresholds()
    print(f"Default thresholds: high={high}, low={low}")
    
    # Test with environment variables set
    os.environ['HIGH_WATER_USAGE'] = '3.0'
    os.environ['LOW_WATER_USAGE'] = '0.3'
    
    high, low = get_water_usage_thresholds()
    print(f"With env vars: high={high}, low={low}")
    
    # Test with invalid values
    os.environ['HIGH_WATER_USAGE'] = 'invalid'
    os.environ['LOW_WATER_USAGE'] = '-1.0'
    
    high, low = get_water_usage_thresholds()
    print(f"With invalid env vars: high={high}, low={low}")
    
    # Clean up
    del os.environ['HIGH_WATER_USAGE']
    del os.environ['LOW_WATER_USAGE']
