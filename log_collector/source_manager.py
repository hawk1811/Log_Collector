"""
Source manager module for handling log sources configuration.
Provides functionality to create, update, and validate sources.
"""
import os
import uuid
import time
import json
import requests
from pathlib import Path

from log_collector.config import (
    logger,
    load_sources,
    save_sources,
    DEFAULT_UDP_PROTOCOL,
    DEFAULT_HEC_BATCH_SIZE,
    DEFAULT_FOLDER_BATCH_SIZE,
    DEFAULT_COMPRESSION_ENABLED,
    DEFAULT_COMPRESSION_LEVEL,
)

class SourceManager:
    """Manages log sources configuration and validation."""
    
    def __init__(self):
        self.sources = load_sources()
    
    def get_sources(self):
        """Get all configured sources."""
        return self.sources
    
    def get_source(self, source_id):
        """Get a specific source by ID."""
        return self.sources.get(source_id)
    
    def add_source(self, source_data):
        """Add a new log source."""
        # Generate a unique ID for the source
        source_id = str(uuid.uuid4())
        
        # Set default values if not provided
        if "protocol" not in source_data:
            source_data["protocol"] = DEFAULT_UDP_PROTOCOL
        
        if source_data.get("target_type") == "HEC" and "batch_size" not in source_data:
            source_data["batch_size"] = DEFAULT_HEC_BATCH_SIZE
        elif source_data.get("target_type") == "FOLDER" and "batch_size" not in source_data:
            source_data["batch_size"] = DEFAULT_FOLDER_BATCH_SIZE
        
        # Check if IP is already in use
        for existing_id, existing_source in self.sources.items():
            if existing_source["source_ip"] == source_data["source_ip"]:
                return {
                    "success": False,
                    "error": f"IP address {source_data['source_ip']} is already used by source '{existing_source['source_name']}'"
                }
        
        # Validate the source before adding
        validation_result = self.validate_source(source_data)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": validation_result["error"]
            }
        
        # Add the source to the collection
        self.sources[source_id] = source_data
        
        # Save the updated sources
        if save_sources(self.sources):
            logger.info(f"Added new source: {source_data['source_name']} (ID: {source_id})")
            return {
                "success": True,
                "source_id": source_id
            }
        else:
            logger.error(f"Failed to save source: {source_data['source_name']}")
            return {
                "success": False,
                "error": "Failed to save source configuration"
            }
    
    def update_source(self, source_id, updated_data):
        """Update an existing log source."""
        if source_id not in self.sources:
            return {
                "success": False,
                "error": f"Source with ID {source_id} does not exist"
            }
        
        # Get existing data and update with new values
        source_data = self.sources[source_id].copy()
        source_data.update(updated_data)
        
        # Check if updated IP is already in use by another source
        if "source_ip" in updated_data:
            new_ip = updated_data["source_ip"]
            for existing_id, existing_source in self.sources.items():
                if existing_id != source_id and existing_source["source_ip"] == new_ip:
                    return {
                        "success": False,
                        "error": f"IP address {new_ip} is already used by source '{existing_source['source_name']}'"
                    }
        
        # Validate the updated source
        validation_result = self.validate_source(source_data)
        if not validation_result["valid"]:
            return {
                "success": False,
                "error": validation_result["error"]
            }
        
        # Update the source
        self.sources[source_id] = source_data
        
        # Save the updated sources
        if save_sources(self.sources):
            logger.info(f"Updated source: {source_data['source_name']} (ID: {source_id})")
            return {
                "success": True
            }
        else:
            logger.error(f"Failed to update source: {source_data['source_name']}")
            return {
                "success": False,
                "error": "Failed to save source configuration"
            }
    
    def delete_source(self, source_id):
        """Delete a log source."""
        if source_id not in self.sources:
            return {
                "success": False,
                "error": f"Source with ID {source_id} does not exist"
            }
        
        source_name = self.sources[source_id]["source_name"]
        del self.sources[source_id]
        
        # Save the updated sources
        if save_sources(self.sources):
            logger.info(f"Deleted source: {source_name} (ID: {source_id})")
            return {
                "success": True
            }
        else:
            logger.error(f"Failed to delete source: {source_name}")
            return {
                "success": False,
                "error": "Failed to save source configuration"
            }
    
    def validate_source(self, source_data):
        """Validate source configuration."""
        required_fields = ["source_name", "source_ip", "listener_port", "target_type"]
        
        # Check required fields
        for field in required_fields:
            if field not in source_data:
                return {
                    "valid": False,
                    "error": f"Missing required field: {field}"
                }
        
        # Validate listener port
        try:
            port = int(source_data["listener_port"])
            if port < 1 or port > 65535:
                return {
                    "valid": False,
                    "error": "Listener port must be between 1 and 65535"
                }
        except ValueError:
            return {
                "valid": False,
                "error": "Listener port must be a valid number"
            }
        
        # Validate protocol
        if source_data.get("protocol") not in ["UDP", "TCP"]:
            return {
                "valid": False,
                "error": "Protocol must be either UDP or TCP"
            }
        
        # Validate target-specific settings
        if source_data["target_type"] == "FOLDER":
            if "folder_path" not in source_data:
                return {
                    "valid": False,
                    "error": "Folder path is required for Folder target"
                }
            
            # Check if folder exists and is accessible
            folder_path = Path(source_data["folder_path"])
            if not folder_path.exists():
                try:
                    os.makedirs(folder_path, exist_ok=True)
                except Exception as e:
                    return {
                        "valid": False,
                        "error": f"Could not create folder path: {str(e)}"
                    }
            
            # Check if folder is writable
            try:
                test_file = folder_path / ".test_write_access"
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Folder is not writable: {str(e)}"
                }
            
            # Validate compression settings if provided
            if "compression_enabled" in source_data and not isinstance(source_data["compression_enabled"], bool):
                return {
                    "valid": False,
                    "error": "compression_enabled must be a boolean value"
                }

            if "compression_level" in source_data:
                try:
                    level = int(source_data["compression_level"])
                    if level < 1 or level > 9:
                        return {
                            "valid": False,
                            "error": "Compression level must be between 1 and 9"
                        }
                except (ValueError, TypeError):
                    return {
                        "valid": False,
                        "error": "Compression level must be a valid integer"
                    }
            
        elif source_data["target_type"] == "HEC":
            if "hec_url" not in source_data:
                return {
                    "valid": False,
                    "error": "HEC URL is required for HEC Connector target"
                }
            
            if "hec_token" not in source_data:
                return {
                    "valid": False,
                    "error": "HEC token is required for HEC Connector target"
                }
            
            # Test HEC connection
            try:
                test_event = {
                    "time": int(time.time()),
                    "event": {
                        "message": "Source Check - OK"
                    },
                    "source": source_data["source_name"]
                }
                
                url = source_data["hec_url"]
                token = source_data["hec_token"]
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "text/plain; charset=utf-8"
                }
                
                response = requests.post(
                    url,
                    data=json.dumps(test_event),
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code != 200:
                    return {
                        "valid": False,
                        "error": f"HEC connection test failed with status code: {response.status_code}"
                    }
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"HEC connection test failed: {str(e)}"
                }
        else:
            return {
                "valid": False,
                "error": "Target type must be either FOLDER or HEC"
            }
        
        # All validations passed
        return {
            "valid": True
        }
