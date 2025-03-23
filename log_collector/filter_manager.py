"""
Filter manager module for Log Collector.
Handles log filter policy management and processing.
"""
import os
import json
import time

from log_collector.config import (
    logger,
)
from log_collector.app_context import get_app_context

# Get app context
app_context = get_app_context()

# Constants
FILTER_FILE = app_context.filter_file

class FilterManager:
    """Manages log filter policies and processing."""
    
    def __init__(self):
        """Initialize the filter manager."""
        self.filters = {}
        self._load_filters()
    
    def _load_filters(self):
        """Load filter policies from file."""
        if not FILTER_FILE.exists():
            logger.info("No filter policies found")
            return
        
        try:
            with open(FILTER_FILE, "r") as f:
                self.filters = json.load(f)
            
            logger.info(f"Loaded {len(self.filters)} filter policies")
        except Exception as e:
            logger.error(f"Error loading filter policies: {e}")
        
    def _save_filters(self):
        """Save filter policies to file."""
        try:
            with open(FILTER_FILE, "w") as f:
                json.dump(self.filters, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving filter policies: {e}")
            return False
    
    def get_all_filters(self):
        """Get all filter policies.
        
        Returns:
            dict: All filters
        """
        return self.filters
    
    def get_source_filters(self, source_id):
        """Get filters for a specific source.
        
        Args:
            source_id: Source ID
            
        Returns:
            list: List of filter rules for the source
        """
        return self.filters.get(source_id, [])
    
    def add_filter(self, source_id, field_name, filter_value):
        """Add a new filter rule.
        
        Args:
            source_id: Source ID
            field_name: Field name to filter on
            filter_value: Value to filter by
            
        Returns:
            bool: Success or failure
        """
        if source_id not in self.filters:
            self.filters[source_id] = []
        
        # Check if filter already exists
        for filter_rule in self.filters[source_id]:
            if filter_rule["field"] == field_name:
                # Update existing filter
                filter_rule["value"] = filter_value
                logger.info(f"Updated filter for source {source_id}, field {field_name}")
                return self._save_filters()
        
        # Add new filter
        self.filters[source_id].append({
            "field": field_name,
            "value": filter_value,
            "enabled": True,
            "created": time.time()
        })
        
        logger.info(f"Added filter for source {source_id}, field {field_name}")
        return self._save_filters()
    
    def remove_filter(self, source_id, field_name):
        """Remove a filter rule.
        
        Args:
            source_id: Source ID
            field_name: Field name to remove filter for
            
        Returns:
            bool: Success or failure
        """
        if source_id not in self.filters:
            return False
        
        # Find and remove the filter
        for i, filter_rule in enumerate(self.filters[source_id]):
            if filter_rule["field"] == field_name:
                del self.filters[source_id][i]
                
                # Remove empty source entries
                if not self.filters[source_id]:
                    del self.filters[source_id]
                
                logger.info(f"Removed filter for source {source_id}, field {field_name}")
                return self._save_filters()
        
        return False
    
    def toggle_filter(self, source_id, field_name):
        """Toggle a filter rule on/off.
        
        Args:
            source_id: Source ID
            field_name: Field name to toggle
            
        Returns:
            bool: Success or failure
        """
        if source_id not in self.filters:
            return False
        
        # Find and toggle the filter
        for filter_rule in self.filters[source_id]:
            if filter_rule["field"] == field_name:
                filter_rule["enabled"] = not filter_rule["enabled"]
                status = "enabled" if filter_rule["enabled"] else "disabled"
                logger.info(f"Filter for source {source_id}, field {field_name} {status}")
                return self._save_filters()
        
        return False
    
    def clear_filters(self, source_id):
        """Clear all filters for a source.
        
        Args:
            source_id: Source ID
            
        Returns:
            bool: Success or failure
        """
        if source_id in self.filters:
            del self.filters[source_id]
            logger.info(f"Cleared all filters for source {source_id}")
            return self._save_filters()
        
        return False
    
    def apply_filters(self, log_str, source_id):
        """Apply filters to decide if a log should be filtered out.
        
        Args:
            log_str: Log string or object
            source_id: Source ID
            
        Returns:
            bool: True if log passes filters (should be kept), False if filtered out
        """
        # If no filters for this source, keep all logs
        if source_id not in self.filters or not self.filters[source_id]:
            return True
        
        # Extract log data for filtering
        log_data = self._extract_log_data(log_str)
        
        # Apply each filter
        for filter_rule in self.filters[source_id]:
            # Skip disabled filters
            if not filter_rule.get("enabled", True):
                continue
            
            field_name = filter_rule["field"]
            filter_value = filter_rule["value"]
            
            # Extract field value using dot notation for nested fields
            field_parts = field_name.split('.')
            value = log_data
            
            try:
                for part in field_parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        # Field not found
                        value = None
                        break
                
                # Convert to string for comparison
                if value is not None:
                    value_str = str(value)
                    
                    # If value matches filter, filter it out
                    if value_str == filter_value:
                        logger.debug(f"Log filtered out: field {field_name} matches value {filter_value}")
                        return False
            except Exception as e:
                logger.error(f"Error applying filter: {e}")
        
        # Log passed all filters
        return True
    
    def _extract_log_data(self, log_str):
        """Extract data from log for filtering.
        
        Args:
            log_str: Log string or object
            
        Returns:
            dict: Extracted log data
        """
        # If already a dict, use it directly
        if isinstance(log_str, dict):
            return log_str
        
        # Try to parse as JSON
        if isinstance(log_str, str):
            try:
                return json.loads(log_str)
            except json.JSONDecodeError:
                # Not JSON, try to extract key=value pairs
                data = {}
                # Simple key=value extraction for filtering
                if "=" in log_str:
                    pairs = log_str.split()
                    for pair in pairs:
                        if "=" in pair:
                            key, value = pair.split("=", 1)
                            data[key.strip()] = value.strip()
                return data
        
        # Fallback
        return {}
