#!/usr/bin/env python3
"""
Zone Configuration Management

Centralized configuration for irrigation zones and their properties.
This replaces hardcoded values in the database manager.

Author: AI Assistant
Date: 2025-01-27
"""

import json
import logging
import os
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class ZoneConfiguration:
    """Manages irrigation zone configuration data"""
    
    def __init__(self, config_file: str = None):
        """Initialize zone configuration
        
        Args:
            config_file: Path to JSON configuration file (optional)
        """
        self.config_file = config_file or os.path.join('config', 'zones.json')
        self._zones_data = None
        self._flow_rates = None
        
    def get_zones_data(self) -> List[Tuple]:
        """Get basic zone configuration data
        
        Returns:
            List of tuples: (zone_id, name, flow_rate_gpm, priority, plant_type)
        """
        if self._zones_data is None:
            self._load_configuration()
        return self._zones_data
    
    def get_average_flow_rates(self) -> Dict[int, float]:
        """Get average flow rates for water usage estimation
        
        Returns:
            Dictionary mapping zone_id to average flow rate (GPM)
        """
        if self._flow_rates is None:
            self._load_configuration()
        return self._flow_rates
    
    def get_zone_flow_rate(self, zone_id: int) -> Optional[float]:
        """Get average flow rate for a specific zone
        
        Args:
            zone_id: Zone ID to look up
            
        Returns:
            Average flow rate in GPM, or None if not found
        """
        flow_rates = self.get_average_flow_rates()
        return flow_rates.get(zone_id)
    
    def _load_configuration(self):
        """Load configuration from file or use defaults"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                self._zones_data = []
                self._flow_rates = {}
                
                for zone_config in config.get('zones', []):
                    zone_id = zone_config['zone_id']
                    name = zone_config['name']
                    flow_rate_gpm = zone_config.get('flow_rate_gpm')
                    priority = zone_config.get('priority', 'MEDIUM')
                    plant_type = zone_config.get('plant_type', 'unknown')
                    average_flow_rate = zone_config.get('average_flow_rate')
                    
                    self._zones_data.append((zone_id, name, flow_rate_gpm, priority, plant_type))
                    
                    if average_flow_rate is not None:
                        self._flow_rates[zone_id] = average_flow_rate
                        
                logger.info(f"Loaded configuration for {len(self._zones_data)} zones from {self.config_file}")
                
            else:
                # Use default configuration if file doesn't exist
                self._load_default_configuration()
                logger.warning(f"Configuration file {self.config_file} not found, using defaults")
                
        except Exception as e:
            logger.error(f"Failed to load zone configuration: {e}")
            self._load_default_configuration()
    
    def _load_default_configuration(self):
        """Load default zone configuration as fallback"""
        # Default configuration based on your provided data
        default_zones = [
            {"zone_id": 1, "name": "Front Right Turf", "flow_rate_gpm": 2.5, "priority": "LOW", "plant_type": "turf", "average_flow_rate": 2.5},
            {"zone_id": 2, "name": "Front Turf Across Sidewalk", "flow_rate_gpm": 4.5, "priority": "LOW", "plant_type": "turf", "average_flow_rate": 4.5},
            {"zone_id": 3, "name": "Front Left Turf", "flow_rate_gpm": 3.2, "priority": "LOW", "plant_type": "turf", "average_flow_rate": 3.2},
            {"zone_id": 4, "name": "Front Planters and Pots", "flow_rate_gpm": 1.0, "priority": "HIGH", "plant_type": "planters", "average_flow_rate": 1.0},
            {"zone_id": 5, "name": "Rear Left Turf", "flow_rate_gpm": 2.2, "priority": "LOW", "plant_type": "turf", "average_flow_rate": 2.2},
            {"zone_id": 6, "name": "Rear right turf", "flow_rate_gpm": 5.3, "priority": "LOW", "plant_type": "turf", "average_flow_rate": 5.3},
            {"zone_id": 8, "name": "Rear left Beds at fence", "flow_rate_gpm": 11.3, "priority": "HIGH", "plant_type": "beds", "average_flow_rate": 11.3},
            {"zone_id": 9, "name": "Rear right beds at fence", "flow_rate_gpm": 8.3, "priority": "HIGH", "plant_type": "beds", "average_flow_rate": 8.3},
            {"zone_id": 10, "name": "Rear Left Pots, baskets & Planters", "flow_rate_gpm": 3.9, "priority": "HIGH", "plant_type": "planters", "average_flow_rate": 3.9},
            {"zone_id": 11, "name": "Rear right pots, baskets & Planters", "flow_rate_gpm": 5.7, "priority": "HIGH", "plant_type": "planters", "average_flow_rate": 5.7},
            {"zone_id": 12, "name": "Rear Bed/Planters/ at Pool", "flow_rate_gpm": 1.3, "priority": "MEDIUM", "plant_type": "beds", "average_flow_rate": 1.3},
            {"zone_id": 13, "name": "Front right bed across drive", "flow_rate_gpm": 1.2, "priority": "MEDIUM", "plant_type": "beds", "average_flow_rate": 1.2},
            {"zone_id": 14, "name": "Rear Right Bed at House and Pool", "flow_rate_gpm": 3.0, "priority": "MEDIUM", "plant_type": "beds", "average_flow_rate": 3.0},
            {"zone_id": 15, "name": "rear Left Bed at House", "flow_rate_gpm": 1.2, "priority": "MEDIUM", "plant_type": "beds", "average_flow_rate": 1.2},
            {"zone_id": 16, "name": "Front Color", "flow_rate_gpm": 10.9, "priority": "HIGH", "plant_type": "color", "average_flow_rate": 10.9},
            {"zone_id": 17, "name": "Front Left Beds", "flow_rate_gpm": 2.6, "priority": "MEDIUM", "plant_type": "beds", "average_flow_rate": 2.6},
        ]
        
        self._zones_data = []
        self._flow_rates = {}
        
        for zone_config in default_zones:
            zone_id = zone_config['zone_id']
            name = zone_config['name']
            flow_rate_gpm = zone_config.get('flow_rate_gpm')
            priority = zone_config.get('priority', 'MEDIUM')
            plant_type = zone_config.get('plant_type', 'unknown')
            average_flow_rate = zone_config.get('average_flow_rate')
            
            self._zones_data.append((zone_id, name, flow_rate_gpm, priority, plant_type))
            
            if average_flow_rate is not None:
                self._flow_rates[zone_id] = average_flow_rate
    
    def save_configuration(self, zones_data: List[Dict] = None):
        """Save current configuration to file
        
        Args:
            zones_data: Optional list of zone dictionaries to save
        """
        try:
            # Create config directory if it doesn't exist
            config_dir = os.path.dirname(self.config_file)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            if zones_data is None:
                # Convert current data to saveable format
                zones_data = []
                zone_tuples = self.get_zones_data()
                flow_rates = self.get_average_flow_rates()
                
                for zone_id, name, flow_rate_gpm, priority, plant_type in zone_tuples:
                    zone_data = {
                        'zone_id': zone_id,
                        'name': name,
                        'flow_rate_gpm': flow_rate_gpm,
                        'priority': priority,
                        'plant_type': plant_type,
                        'average_flow_rate': flow_rates.get(zone_id)
                    }
                    zones_data.append(zone_data)
            
            config = {'zones': zones_data}
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"Saved zone configuration to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save zone configuration: {e}")
    
    def update_flow_rate(self, zone_id: int, average_flow_rate: float):
        """Update average flow rate for a zone
        
        Args:
            zone_id: Zone ID to update
            average_flow_rate: New flow rate in GPM
        """
        if self._flow_rates is None:
            self._load_configuration()
            
        self._flow_rates[zone_id] = average_flow_rate
        logger.info(f"Updated average flow rate for zone {zone_id}: {average_flow_rate} GPM")


# Global instance for easy access
zone_config = ZoneConfiguration()


def get_zone_average_flow_rate(zone_id: int) -> Optional[float]:
    """Convenience function to get zone flow rate
    
    Args:
        zone_id: Zone ID to look up
        
    Returns:
        Average flow rate in GPM, or None if not found
    """
    return zone_config.get_zone_flow_rate(zone_id)


def get_all_zones_data() -> List[Tuple]:
    """Convenience function to get all zone data
    
    Returns:
        List of tuples: (zone_id, name, flow_rate_gpm, priority, plant_type)
    """
    return zone_config.get_zones_data()


def get_all_average_flow_rates() -> Dict[int, float]:
    """Convenience function to get all average flow rates
    
    Returns:
        Dictionary mapping zone_id to average flow rate (GPM)
    """
    return zone_config.get_average_flow_rates()

