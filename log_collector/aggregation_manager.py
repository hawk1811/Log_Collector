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
    get_app_context,
)

# Get app context
app_context = get_app_context()

# Constants
POLICY_FILE = app_context.policy_file

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

    def ensure_template(self, source_id, processor_manager):
        """Ensure a log template exists for a source, creating one if needed.
        
        Args:
            source_id: Source ID to check
            processor_manager: Processor manager to get sample logs from
            
        Returns:
            bool: True if template exists or was created, False otherwise
        """
        # Check if we already have a template
        if source_id in self.templates:
            return True
        
        # Try to get a sample log from the queue
        if source_id in processor_manager.queues and not processor_manager.queues[source_id].empty():
            try:
                # Get a copy of the first log without removing it
                queue_items = list(processor_manager.queues[source_id].queue)
                
                # Try to find a non-empty log in the queue
                sample_log = None
                for item in queue_items:
                    if item and (isinstance(item, dict) or (isinstance(item, str) and len(item.strip()) > 0)):
                        sample_log = item
                        break
                
                if sample_log:
                    # Store it as a template
                    template_fields = self.store_log_template(source_id, sample_log)
                    logger.info(f"Auto-saved sample log template for source {source_id} with {len(template_fields)} fields")
                    
                    # Process the sample log right away to extract fields
                    return True
                else:
                    logger.warning(f"No valid logs found in queue for source {source_id}")
                    return False
            except Exception as e:
                logger.error(f"Error auto-saving log template for source {source_id}: {e}")
                return False
        
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
            
            # Try to parse based on format patterns
            if "=" in log_content:
                # Key=value format
                self._extract_key_value_pairs(log_content, fields)
            elif ":" in log_content and not log_content.strip().startswith("{"):
                # Key: value format (but not JSON)
                self._extract_colon_separated(log_content, fields)
            elif "\t" in log_content:
                # Tab-separated format
                self._extract_delimited(log_content, "\t", fields)
            elif ";" in log_content:
                # Semicolon-separated format
                self._extract_delimited(log_content, ";", fields)
            elif "," in log_content and not ('"' in log_content and ',' in log_content):
                # Comma-separated format (but avoid CSV with quotes)
                self._extract_delimited(log_content, ",", fields)
            elif "|" in log_content:
                # Pipe-separated format
                self._extract_delimited(log_content, "|", fields)
            else:
                # Space-separated values or free-form text
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
                # Store lists with more detail
                value_str = str(value)[:100] if value else "[]"
                if value and len(value) > 0:
                    # Include sample item type
                    item_type = type(value[0]).__name__ if len(value) > 0 else "unknown"
                    
                    # Handle list of dicts specially
                    if isinstance(value[0], dict) and len(value[0]) <= 5:
                        # Show basic structure for small dicts
                        keys_str = ", ".join(list(value[0].keys()))
                        value_str = f"List of objects with keys: {keys_str}"
                        item_type = "object"
                    
                    fields[field_name] = {
                        "type": f"list<{item_type}>",
                        "example": value_str,
                        "length": len(value)
                    }
                else:
                    fields[field_name] = {
                        "type": "list",
                        "example": "[]",
                        "length": 0
                    }
            else:
                # Store primitive values with more detail
                type_name = type(value).__name__
                example = str(value)
                
                # Truncate very long values
                if len(example) > 100:
                    example = example[:97] + "..."
                
                # Add length info for strings
                if type_name == "str":
                    fields[field_name] = {
                        "type": type_name,
                        "example": example,
                        "length": len(str(value))
                    }
                # Add numeric formatting for numbers
                elif type_name in ["int", "float"]:
                    fields[field_name] = {
                        "type": type_name,
                        "example": example,
                        "formatted": f"{value:,}" if type_name == "int" else f"{value:.2f}"
                    }
                else:
                    fields[field_name] = {
                        "type": type_name,
                        "example": example
                    }
    
    def _extract_key_value_pairs(self, log_content, fields):
        """Extract fields from key=value pairs format with enhanced delimiter detection.
        
        Args:
            log_content: Log string with key=value pairs
            fields: Fields dictionary to populate
        """
        # Handle different delimiters between key-value pairs
        found_pairs = 0
        
        # First, try to extract common structured fields like timestamp, level, etc.
        import re
        
        # Look for timestamp
        timestamp_patterns = [
            (r'\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:?\d{2})?)\b', 'ISO8601'),
            (r'\b(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\b', 'datetime'),
            (r'\b(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\b', 'MM/DD/YYYY'),
            (r'\b(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\b', 'Syslog'),
            (r'\b(\d{2}-\w{3}-\d{4}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\b', 'DD-MMM-YYYY')
        ]
        
        for pattern, time_format in timestamp_patterns:
            match = re.search(pattern, log_content)
            if match:
                timestamp = match.group(1)
                fields["timestamp"] = {
                    "type": "timestamp",
                    "format": time_format,
                    "example": timestamp,
                    "formatted": timestamp
                }
                break
        
        # Look for log levels
        log_level_pattern = r'\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|TRACE)\b'
        level_match = re.search(log_level_pattern, log_content, re.IGNORECASE)
        if level_match:
            level = level_match.group(1).upper()
            fields["log_level"] = {
                "type": "level",
                "example": level,
                "formatted": level
            }
        
        # Try to detect the primary delimiter by counting occurrences
        delimiter_counts = {}
        for delimiter in [' ', ',', ';', '|', '\t', ' = ']:
            delimiter_counts[delimiter] = log_content.count(delimiter)
        
        # Sort delimiters by count (most common first)
        sorted_delimiters = sorted(delimiter_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Define all possible key-value separators to try
        kv_separators = ['=', ':', '->', '=>', ' - ']
        
        # Try each delimiter/separator combination
        for delimiter, _ in sorted_delimiters:
            if delimiter == ' = ':
                # Special case for space around equals
                pairs = log_content.split(' = ')
                if len(pairs) > 1:
                    # Reconstruct into key=value pairs with proper splitting
                    new_pairs = []
                    current_key = pairs[0].strip()
                    
                    for i in range(1, len(pairs)):
                        parts = pairs[i].strip().split(' ', 1)
                        if len(parts) > 1:
                            value = parts[0]
                            next_key = parts[1]
                            new_pairs.append(f"{current_key}={value}")
                            current_key = next_key
                        else:
                            # Last value without a new key
                            new_pairs.append(f"{current_key}={parts[0]}")
                    
                    pairs = new_pairs
                    kv_separator = '='  # Using equals as separator
                    
                    for pair in pairs:
                        key, value = pair.split(kv_separator, 1)
                        self._add_key_value_field(key.strip(), value.strip(), fields)
                        found_pairs += 1
                    
                    # If we found pairs, we're done
                    if found_pairs > 0:
                        return
            else:
                # Standard delimiter splitting
                parts = log_content.split(delimiter)
                
                # Try each key-value separator with this delimiter
                for kv_separator in kv_separators:
                    temp_found = 0
                    
                    for part in parts:
                        part = part.strip()
                        if kv_separator in part:
                            # Split at first occurrence only
                            key_value = part.split(kv_separator, 1)
                            if len(key_value) == 2:
                                key, value = key_value
                                key = key.strip()
                                value = value.strip()
                                
                                # Skip empty keys or values
                                if not key or not value:
                                    continue
                                
                                self._add_key_value_field(key, value, fields)
                                temp_found += 1
                    
                    # If this separator worked well, use it
                    if temp_found > 0:
                        found_pairs += temp_found
                        # Don't break yet, try other separators with same delimiter
                
                # If we found pairs with this delimiter, move to next
                if found_pairs > 0:
                    continue
        
        # If we didn't find key=value pairs with standard methods,
        # look for patterns in the form of multi-line "key: value"
        if found_pairs == 0:
            multi_line_pattern = re.compile(r'^([A-Za-z][A-Za-z0-9_\-\.]*)\s*[:=]\s*(.+?)$', re.MULTILINE)
            matches = multi_line_pattern.findall(log_content)
            
            for key, value in matches:
                key = key.strip()
                value = value.strip()
                
                # Skip empty keys or values
                if not key or not value:
                    continue
                    
                self._add_key_value_field(key, value, fields)
                found_pairs += 1
        
        # If there's still no fields found, try to find field=value patterns within tokens
        if found_pairs == 0:
            # This will match patterns like field1=value1;field2=value2 or field1="value1",field2="value2"
            pattern = re.compile(r'([A-Za-z][A-Za-z0-9_\-\.]*)=(?:"([^"]*)"|([^,;\s]*))')
            matches = pattern.findall(log_content)
            
            for match in matches:
                key = match[0].strip()
                # Value is either in group 1 (quoted) or group 2 (unquoted)
                value = match[1] if match[1] else match[2]
                value = value.strip()
                
                # Skip empty keys or values
                if not key or not value:
                    continue
                    
                self._add_key_value_field(key, value, fields)
                found_pairs += 1
    
    def _add_key_value_field(self, key, value, fields):
        """Helper method to add a key-value pair to fields with type detection.
        
        Args:
            key: Field key
            value: Field value
            fields: Fields dictionary to populate
        """
        # Try to detect value type
        value_type = "string"
        formatted = value
        
        try:
            int_val = int(value)
            value_type = "int"
            formatted = f"{int_val:,}"
        except ValueError:
            try:
                float_val = float(value)
                value_type = "float"
                formatted = f"{float_val:.2f}"
            except ValueError:
                # Check for boolean values
                if value.lower() in ('true', 'false'):
                    value_type = "bool"
                    formatted = value
                elif value.lower() in ('yes', 'no'):
                    value_type = "bool"
                    formatted = "true" if value.lower() == "yes" else "false"
                elif key.lower() in ('time', 'timestamp', 'date'):
                    value_type = "timestamp"
                    formatted = value
                elif key.lower() in ('level', 'severity', 'loglevel'):
                    value_type = "level"
                    formatted = value
                else:
                    # If the value is longer than 40 chars, truncate it for display
                    if len(formatted) > 40:
                        formatted = formatted[:37] + "..."
        
        # Store field with detected type
        fields[key] = {
            "type": value_type,
            "example": value,
            "formatted": formatted,
            "original": value
        }
    
    def _extract_delimited(self, log_content, delimiter, fields):
        """Extract fields from a delimited string.
        
        Args:
            log_content: Log string with delimited values
            delimiter: Delimiter character
            fields: Fields dictionary to populate
        """
        # Check if the first line looks like a header
        lines = log_content.strip().split("\n")
        
        if len(lines) > 1:
            # Multi-line delimited file, treat first line as header
            header = lines[0].split(delimiter)
            data = lines[1].split(delimiter)
            
            # Match header fields with data
            for i, field_name in enumerate(header):
                field_name = field_name.strip()
                if not field_name:
                    continue
                    
                if i < len(data):
                    value = data[i].strip()
                    
                    # Try to determine value type
                    value_type = "string"
                    formatted = value
                    
                    try:
                        int_val = int(value)
                        value_type = "int"
                        formatted = f"{int_val:,}"
                    except ValueError:
                        try:
                            float_val = float(value)
                            value_type = "float"
                            formatted = f"{float_val:.2f}"
                        except ValueError:
                            if value.lower() in ('true', 'false', 'yes', 'no'):
                                value_type = "bool"
                            elif field_name.lower() in ('time', 'timestamp', 'date'):
                                value_type = "timestamp"
                            elif field_name.lower() in ('level', 'severity', 'loglevel'):
                                value_type = "level"
                            
                            # If the value is longer than 40 chars, truncate it for display
                            if len(formatted) > 40:
                                formatted = formatted[:37] + "..."
                    
                    fields[field_name] = {
                        "type": value_type,
                        "example": value,
                        "formatted": formatted
                    }
        else:
            # Single line delimited string
            parts = log_content.split(delimiter)
            
            # Process as unnamed fields
            for i, value in enumerate(parts):
                value = value.strip()
                if not value:
                    continue
                    
                field_name = f"field_{i+1}"
                
                # Check if value contains a key=value pattern
                if "=" in value and not value.startswith("=") and not value.endswith("="):
                    key, val = value.split("=", 1)
                    field_name = key.strip()
                    value = val.strip()
                
                # Try to determine value type
                value_type = "string"
                formatted = value
                
                try:
                    int_val = int(value)
                    value_type = "int"
                    formatted = f"{int_val:,}"
                except ValueError:
                    try:
                        float_val = float(value)
                        value_type = "float"
                        formatted = f"{float_val:.2f}"
                    except ValueError:
                        if value.lower() in ('true', 'false', 'yes', 'no'):
                            value_type = "bool"
                        
                        # If the value is longer than 40 chars, truncate it for display
                        if len(formatted) > 40:
                            formatted = formatted[:37] + "..."
                
                fields[field_name] = {
                    "type": value_type,
                    "example": value,
                    "formatted": formatted
                }
    
    def _extract_colon_separated(self, log_content, fields):
        """Extract fields from colon-separated format (key: value).
        
        Args:
            log_content: Log string with colon-separated key-value pairs
            fields: Fields dictionary to populate
        """
        import re
        
        # Look for patterns like "key: value" across multiple lines
        pattern = re.compile(r'([^:]+):\s*(.+?)(?=\n[^:]+:|\n*$)', re.DOTALL)
        matches = pattern.findall(log_content)
        
        for key, value in matches:
            key = key.strip()
            value = value.strip()
            
            if not key or not value:
                continue
            
            # Try to determine value type
            value_type = "string"
            formatted = value
            
            try:
                int_val = int(value)
                value_type = "int"
                formatted = f"{int_val:,}"
            except ValueError:
                try:
                    float_val = float(value)
                    value_type = "float"
                    formatted = f"{float_val:.2f}"
                except ValueError:
                    if value.lower() in ('true', 'false', 'yes', 'no'):
                        value_type = "bool"
                    elif key.lower() in ('time', 'timestamp', 'date'):
                        value_type = "timestamp"
                    elif key.lower() in ('level', 'severity', 'loglevel'):
                        value_type = "level"
                    
                    # If the value is longer than 40 chars, truncate it for display
                    if len(formatted) > 40:
                        formatted = formatted[:37] + "..."
            
            fields[key] = {
                "type": value_type,
                "example": value,
                "formatted": formatted
            }
    
    def _extract_space_separated(self, log_content, fields):
        """Extract fields from space-separated values.
        
        Args:
            log_content: Space-separated log string
            fields: Fields dictionary to populate
        """
        # First try to detect if this is a structured log with standard patterns
        
        # Check for timestamp at the beginning (common in many logs)
        timestamp_patterns = [
            r'^\d{4}-\d{2}-\d{2}', # ISO date (YYYY-MM-DD)
            r'^\d{2}:\d{2}:\d{2}', # Time (HH:MM:SS)
            r'^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', # Syslog format (Mon DD HH:MM:SS)
            r'^\d{2}/\d{2}/\d{4}', # Date (MM/DD/YYYY)
        ]
        
        import re
        has_timestamp = False
        timestamp_value = ""
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, log_content)
            if match:
                has_timestamp = True
                timestamp_value = match.group(0)
                break
        
        # If we found a timestamp, extract it as a special field
        if has_timestamp:
            fields["timestamp"] = {
                "type": "timestamp",
                "example": timestamp_value,
                "formatted": timestamp_value
            }
        
        # Look for log levels
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "WARN", "TRACE", "FATAL"]
        found_level = None
        
        for level in log_levels:
            if f" {level} " in f" {log_content} ":
                found_level = level
                fields["log_level"] = {
                    "type": "level",
                    "example": level,
                    "formatted": level
                }
                break
        
        # Try to detect if there's a message section (usually after a colon or in square brackets)
        message_match = re.search(r':\s*(.+)$', log_content)
        if message_match:
            message = message_match.group(1).strip()
            fields["message"] = {
                "type": "string",
                "example": message,
                "formatted": message if len(message) < 40 else message[:37] + "..."
            }
        
        # Look for IP addresses
        ip_matches = re.findall(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', log_content)
        if ip_matches:
            fields["ip_address"] = {
                "type": "ip",
                "example": ip_matches[0],
                "formatted": ip_matches[0]
            }
        
        # Now process the remaining content as space-separated fields
        values = log_content.split()
        
        # Skip the first fields if we found a timestamp
        start_idx = 0
        if has_timestamp:
            # Skip the timestamp parts (could be multiple tokens)
            timestamp_parts = timestamp_value.split()
            start_idx = len(timestamp_parts)
        
        # Process each token as a field
        for i, value in enumerate(values[start_idx:], start_idx):
            # Skip the log level if we found one
            if found_level and value == found_level:
                continue
            
            # Skip if this value is already captured in another field
            skip = False
            for field_data in fields.values():
                if field_data.get("example") == value:
                    skip = True
                    break
            
            if skip:
                continue
                
            field_name = f"field_{i+1}"
            
            # Check for field=value format within a token
            if "=" in value and not value.startswith("=") and not value.endswith("="):
                key, val = value.split("=", 1)
                field_name = key.strip()
                value = val.strip()
            
            # Try to detect the value type
            value_type = "string"
            try:
                int_val = int(value)
                value_type = "int"
                formatted = f"{int_val:,}"
            except ValueError:
                try:
                    float_val = float(value)
                    value_type = "float"
                    formatted = f"{float_val:.2f}"
                except ValueError:
                    # Check for boolean values
                    if value.lower() in ('true', 'false'):
                        value_type = "bool"
                        formatted = value
                    else:
                        formatted = value
                        
                        # If the value is longer than 40 chars, truncate it for display
                        if len(formatted) > 40:
                            formatted = formatted[:37] + "..."
            
            fields[field_name] = {
                "type": value_type,
                "example": value,
                "formatted": formatted
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
        
    def delete_template(self, source_id):
        """Delete a log template.
        
        Args:
            source_id: Source ID
            
        Returns:
            bool: Success or failure
        """
        if source_id not in self.templates:
            logger.error(f"No template found for source {source_id}")
            return False
        
        # Delete the template
        del self.templates[source_id]
        
        # Also delete any associated policy since it depends on the template
        if source_id in self.policies:
            del self.policies[source_id]
            logger.info(f"Also deleted associated policy for source {source_id}")
        
        # Save changes
        result = self._save_policies()
        if result:
            logger.info(f"Deleted template for source {source_id}")
        
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
