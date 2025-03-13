"""
Health check module for monitoring system resources and source statuses.
"""
import os
import json
import time
import threading
import requests
import psutil

from log_collector.config import (
    logger,
    DEFAULT_HEALTH_CHECK_INTERVAL,
)

class HealthCheck:
    """Manages system health monitoring and reporting."""
    
    def __init__(self, source_manager, processor_manager):
        """Initialize health check monitor.
        
        Args:
            source_manager: Instance of SourceManager to access source configs
            processor_manager: Instance of ProcessorManager to access queue stats
        """
        self.source_manager = source_manager
        self.processor_manager = processor_manager
        self.config = None
        self.thread = None
        self.running = False
    
    def configure(self, hec_url, hec_token, interval=DEFAULT_HEALTH_CHECK_INTERVAL):
        """Configure health check settings.
        
        Args:
            hec_url: URL for HEC endpoint
            hec_token: Token for HEC authentication
            interval: Reporting interval in seconds
        """
        self.config = {
            "hec_url": hec_url,
            "hec_token": hec_token,
            "interval": int(interval)
        }
        
        # Test connection
        if not self._test_connection():
            logger.error("Health check configuration failed: Connection test failed")
            self.config = None
            return False
        
        logger.info("Health check configured successfully")
        return True
    
    def start(self):
        """Start health check monitoring."""
        if not self.config:
            logger.error("Cannot start health check: Not configured")
            return False
        
        if self.running:
            logger.warning("Health check already running")
            return True
        
        self.running = True
        self.thread = threading.Thread(
            target=self._monitor_thread,
            daemon=True
        )
        self.thread.start()
        logger.info("Health check monitoring started")
        return True
    
    def stop(self):
        """Stop health check monitoring."""
        if not self.running:
            logger.warning("Health check not running")
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        
        logger.info("Health check monitoring stopped")
    
    def _test_connection(self):
        """Test connection to HEC endpoint.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        if not self.config:
            return False
        
        try:
            test_event = {
                "time": int(time.time()),
                "event": {
                    "message": "Health Check Connector - OK"
                },
                "source": "Heartbeat"
            }
            
            headers = {
                "Authorization": f"Bearer {self.config['hec_token']}",
                "Content-Type": "text/plain; charset=utf-8"
            }
            
            response = requests.post(
                self.config["hec_url"],
                data=json.dumps(test_event),
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Health check connection test failed: {e}")
            return False
    
    def _monitor_thread(self):
        """Background thread for periodic health monitoring."""
        logger.info("Health check monitor thread started")
        
        while self.running:
            try:
                # Collect health data
                health_data = self._collect_health_data()
                
                # Send health data
                self._send_health_data(health_data)
                
                # Wait for next interval
                time.sleep(self.config["interval"])
            
            except Exception as e:
                logger.error(f"Error in health check monitor: {e}")
                time.sleep(self.config["interval"])  # Wait before retrying
        
        logger.info("Health check monitor thread stopped")
    
    def _collect_health_data(self):
        """Collect system health data.
        
        Returns:
            dict: Health data metrics
        """
        # Collect CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_load = [x / cpu_count * 100 for x in psutil.getloadavg()] if hasattr(psutil, "getloadavg") else None
        
        # Collect memory metrics
        memory = psutil.virtual_memory()
        
        # Collect disk metrics
        disk = psutil.disk_usage("/")
        
        # Collect network metrics
        net_io = psutil.net_io_counters()
        
        # Collect source stats
        sources = self.source_manager.get_sources()
        source_stats = {}
        
        for source_id, source in sources.items():
            # Get queue size if available
            queue_size = 0
            if source_id in self.processor_manager.queues:
                queue_size = self.processor_manager.queues[source_id].qsize()
            
            # Count active processors
            active_processors = sum(1 for p_id, p_thread in self.processor_manager.processors.items()
                                  if p_id.startswith(f"{source_id}:") and p_thread.is_alive())
            
            source_stats[source["source_name"]] = {
                "queue_size": queue_size,
                "active_processors": active_processors,
                "listener_port": source["listener_port"],
                "protocol": source["protocol"],
                "target_type": source["target_type"]
            }
        
        # Build complete health data
        health_data = {
            "time": int(time.time()),
            "event": {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "load": cpu_load
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                "sources": source_stats,
                "pid": os.getpid(),
                "process_memory": psutil.Process(os.getpid()).memory_info().rss
            },
            "source": "Heartbeat"
        }
        
        return health_data
    
    def _send_health_data(self, health_data):
        """Send health data to HEC.
        
        Args:
            health_data: Health metrics data to send
        """
        if not self.config:
            logger.error("Cannot send health data: Not configured")
            return
        
        try:
            headers = {
                "Authorization": f"Bearer {self.config['hec_token']}",
                "Content-Type": "text/plain; charset=utf-8"
            }
            
            response = requests.post(
                self.config["hec_url"],
                data=json.dumps(health_data),
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Error sending health data: HTTP {response.status_code}, {response.text}")
        
        except Exception as e:
            logger.error(f"Error sending health data: {e}")