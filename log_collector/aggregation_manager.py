"""
Aggregation manager module for Log Collector.
Handles log aggregation policy management and processing.
"""
import os
import json
import time
from pathlib import Path
import hashlib

from log_collector.config import (
    logger,
    DATA_DIR,
)

# Constants
POLICY_FILE = DATA_DIR / "policy.json"

class AggregationManager:
    """Manages log aggregation policies and processing."""
    
    def __init__(self):
        """Initialize the aggregation manager."""
        self.policies = {}
        self.templates = {}
        self._load_policies()
    
    def _load_policies(self):
        """Load aggregation policies from file."""
        if not POLICY_FILE.exists():
            logger.info("No aggregation policies found")
            return
        
        try:
            with open(POLICY_FILE, "r") as f:
                data = json.load(f)
                self.policies = data.get("policies", {})
                self.templates = data.get("templates", {})
            
            logger.info(f"Loaded {len(self.policies)} aggregation policies")
        except Exception as e:
            logger.error(f"Error loading aggregation policies: {e}")
    
    def _save_policies(self):
        """Save aggregation policies to file."""
        try:
            data = {
                "policies": self.policies,
                "templates": self.templates
            }
            
            with open(POLICY_FILE, "w") as f:
                json.dump(data, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving aggregation policies: {e}")
            return False
    
    def store_log_template(self, source_id, log_content):
        """Store a log template for a source.
        
        Args:
            source_id: Source ID
            log_content: Log content (string or dict)
            
        Returns:
            dict: Parsed fields from the log
        """
        try:
            # Parse log fields
            fields = self._extract_fields(log_content)
            
            # Store as template
            self.templates[source_id] = {
                "log": log_content,
                "fields": fields,
                "timestamp": time.time()
            }
            
            # Save updated templates
            self._save_policies()
            
            return fields
        except Exception as e:
            logger.error(f"Error storing log template: {e}")
            return {}
    
    def _extract_fields(self, log_content):
        """Extract fields from log content.
        
        Args:
            log_content: Log content (string or dict)
            
        Returns:
            dict: Extracted fields with their values and types
        """
        fields = {}
        
        # Try to parse as JSON
        if isinstance(log_content, dict):
            # Already a dict (parsed JSON)
            self._extract_fields_from_dict(log_content, fields)
        else:
            # Try to parse as JSON string
            try:
                json_obj = json.loads(log_content)
                self._extract_fields_from_dict(json_obj, fields)
                return fields
            except json.JSONDecodeError:
                pass
            
            # Try to parse as key=value pairs
            if "=" in log_content:
                self._extract_key_value_pairs(log_content, fields)
            else:
                # Space-separated values
                self._extract_space_separated(log_content, fields)
        
        return fields
    
    def _extract_fields_from_dict(self, data, fields, prefix=""):
        """Recursively extract fields from dictionary.
        
        Args:
            data: Dictionary to extract fields from
            fields: Fields dictionary to populate
            prefix: Prefix for nested fields
        """
        for key, value in data.items():
            field_name = f"{prefix}{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recursively process nested dictionaries
                self._extract_fields_from_dict(value, fields, f"{field_name}.")
            elif isinstance(value, list):
                # Store lists as a type but don't expand
                fields[field_name] = {
                    "type": "list",
                    "example": str(value)[:100] if value else "[]"
                }
            else:
                # Store primitive values
                fields[field_name] = {
                    "type": type(value).__name__,
                    "example": str(value)
                }
    
    def _extract_key_value_pairs(self, log_content, fields):
        """Extract fields from key=value pairs format.
        
        Args:
            log_content: Log string with key=value pairs
            fields: Fields dictionary to populate
        """
        # Handle different delimiters between key-value pairs
        for delimiter in [' ', ',', ';']:
            pairs = log_content.split(delimiter)
            if len(pairs) > 1:
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        fields[key] = {
                            "type": "string",
                            "example": value
                        }
    
    def _extract_space_separated(self, log_content, fields):
        """Extract fields from space-separated values.
        
        Args:
            log_content: Space-separated log string
            fields: Fields dictionary to populate
        """
        values = log_content.split()
        for i, value in enumerate(values):
            field_name = f"field_{i+1}"
            fields[field_name] = {
                "type": "string",
                "example": value
            }
    
    def create_policy(self, source_id, selected_fields):
        """Create or update an aggregation policy.
        
        Args:
            source_id: Source ID
            selected_fields: List of field names to use for aggregation
            
        Returns:
            bool: Success or failure
        """
        if source_id not in self.templates:
            logger.error(f"No template found for source {source_id}")
            return False
        
        # Create the policy
        self.policies[source_id] = {
            "fields": selected_fields,
            "created": time.time(),
            "enabled": True
        }
        
        # Save policies
        result = self._save_policies()
        if result:
            logger.info(f"Created aggregation policy for source {source_id}")
        
        return result
    
    def update_policy(self, source_id, updates):
        """Update an existing policy.
        
        Args:
            source_id: Source ID
            updates: Dictionary of updates
            
        Returns:
            bool: Success or failure
        """
        if source_id not in self.policies:
            logger.error(f"No policy found for source {source_id}")
            return False
        
        # Update policy fields
        for key, value in updates.items():
            self.policies[source_id][key] = value
        
        # Save policies
        result = self._save_policies()
        if result:
            logger.info(f"Updated aggregation policy for source {source_id}")
        
        return result
    
    def delete_policy(self, source_id):
        """Delete an aggregation policy.
        
        Args:
            source_id: Source ID
            
        Returns:
            bool: Success or failure
        """
        if source_id not in self.policies:
            logger.error(f"No policy found for source {source_id}")
            return False
        
        # Delete the policy
        del self.policies[source_id]
        
        # Save policies
        result = self._save_policies()
        if result:
            logger.info(f"Deleted aggregation policy for source {source_id}")
        
        return result
    
    def get_policy(self, source_id):
        """Get an aggregation policy.
        
        Args:
            source_id: Source ID
            
        Returns:
            dict: Policy or None
        """
        return self.policies.get(source_id)
    
    def get_template(self, source_id):
        """Get a log template.
        
        Args:
            source_id: Source ID
            
        Returns:
            dict: Template or None
        """
        return self.templates.get(source_id)
    
    def get_all_policies(self):
        """Get all aggregation policies.
        
        Returns:
            dict: All policies
        """
        return self.policies
    
    def aggregate_batch(self, batch, source_id):
        """Aggregate a batch of logs based on policy.
        
        Args:
            batch: List of log strings
            source_id: Source ID
            
        Returns:
            list: Aggregated batch of logs
        """
        # Check if there's a policy for this source
        policy = self.get_policy(source_id)
        if not policy or not policy.get("enabled", False):
            return batch
        
        # Get aggregation fields from policy
        agg_fields = policy["fields"]
        if not agg_fields:
            return batch
        
        # Initialize aggregation map
        aggregation_map = {}
        
        # Process each log for aggregation
        for log_str in batch:
            try:
                # Extract key data from the log
                agg_key, log_data = self._extract_aggregation_key(log_str, agg_fields)
                
                if agg_key:
                    # Add to aggregation map
                    if agg_key not in aggregation_map:
                        aggregation_map[agg_key] = {
                            "count": 1,
                            "first_time": time.time(),
                            "last_time": time.time(),
                            "base_log": log_data,
                            "original_str": log_str
                        }
                    else:
                        aggregation_map[agg_key]["count"] += 1
                        aggregation_map[agg_key]["last_time"] = time.time()
                else:
                    # Keep logs that couldn't be aggregated as-is
                    if "non_aggregated" not in aggregation_map:
                        aggregation_map["non_aggregated"] = []
                    aggregation_map["non_aggregated"].append(log_str)
            
            except Exception as e:
                logger.error(f"Error processing log for aggregation: {e}")
                # Keep logs that caused errors as-is
                if "non_aggregated" not in aggregation_map:
                    aggregation_map["non_aggregated"] = []
                aggregation_map["non_aggregated"].append(log_str)
        
        # Build the aggregated batch
        aggregated_batch = []
        
        # Add aggregated logs
        for agg_key, agg_data in aggregation_map.items():
            if agg_key == "non_aggregated":
                # Add all non-aggregated logs as-is
                aggregated_batch.extend(agg_data)
                continue
                
            # For aggregated logs
            if agg_data["count"] > 1:
                # Create an enhanced log with aggregation metadata
                try:
                    if isinstance(agg_data["base_log"], dict):
                        # Create a new dict with aggregation metadata
                        aggregated_log = agg_data["base_log"].copy()
                        aggregated_log["is_aggregated"] = "yes"
                        aggregated_log["first_log_time"] = agg_data["first_time"]
                        aggregated_log["last_log_time"] = agg_data["last_time"]
                        aggregated_log["total_logs_aggregated"] = agg_data["count"]
                        
                        # Convert back to string if needed
                        if isinstance(agg_data["original_str"], str):
                            aggregated_batch.append(json.dumps(aggregated_log))
                        else:
                            aggregated_batch.append(aggregated_log)
                    else:
                        # For string logs, just add metadata
                        enhanced_str = agg_data["original_str"]
                        enhanced_str += f" [Aggregated: {agg_data['count']} logs]"
                        aggregated_batch.append(enhanced_str)
                except Exception as e:
                    logger.error(f"Error creating aggregated log: {e}")
                    # Fall back to original string on error
                    aggregated_batch.append(agg_data["original_str"])
            else:
                # If only one log matched this key, keep the original
                aggregated_batch.append(agg_data["original_str"])
        
        logger.info(f"Aggregation reduced {len(batch)} logs to {len(aggregated_batch)} for source {source_id}")
        return aggregated_batch
    
    def _extract_aggregation_key(self, log_str, agg_fields):
        """Extract aggregation key from a log.
        
        Args:
            log_str: Log string
            agg_fields: Fields to use for aggregation
            
        Returns:
            tuple: (aggregation_key, log_data)
        """
        # Parse the log data
        log_data = {}
        try:
            # Try to parse as JSON
            if isinstance(log_str, str):
                try:
                    json_data = json.loads(log_str)
                    log_data = json_data
                except json.JSONDecodeError:
                    # Parse using the same logic as template extraction
                    fields = {}
                    if "=" in log_str:
                        self._extract_key_value_pairs(log_str, fields)
                    else:
                        self._extract_space_separated(log_str, fields)
                    
                    # Create a simple log data object from fields
                    for field_name, field_info in fields.items():
                        log_data[field_name] = field_info["example"]
            else:
                # Already a dict
                log_data = log_str
            
            # Create an aggregation key based on the selected fields
            agg_values = []
            for field in agg_fields:
                # Handle nested fields with dot notation
                field_parts = field.split('.')
                value = log_data
                for part in field_parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = None
                        break
                
                # Add field value to aggregation key
                agg_values.append(str(value) if value is not None else "None")
            
            # Create a unique key for this combination of values
            if agg_values:
                agg_key = hashlib.md5("|".join(agg_values).encode()).hexdigest()
                return agg_key, log_data
            
            return None, log_data
        
        except Exception as e:
            logger.error(f"Error extracting aggregation key: {e}")
            return None, log_str
