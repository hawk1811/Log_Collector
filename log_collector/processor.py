"""
Processor module for handling log processing and delivery.
Manages queues, batching, and delivery to targets.
"""
import os
import json
import time
import threading
import queue
import requests
import gzip  # Added for compression
from datetime import datetime
from pathlib import Path

from log_collector.config import (
    logger,
    DEFAULT_QUEUE_LIMIT,
    DEFAULT_COMPRESSION_ENABLED,
    DEFAULT_COMPRESSION_LEVEL,
)

# Maximum time (in seconds) to wait before flushing a partial batch
MAX_FLUSH_INTERVAL = 60

class ProcessorManager:
    """Manages log processing queues and worker threads."""
    
    def __init__(self, source_manager, aggregation_manager=None):
        """Initialize the processor manager.
        
        Args:
            source_manager: Instance of SourceManager to access source configs
            aggregation_manager: Optional instance of AggregationManager for log aggregation
        """
        self.source_manager = source_manager
        self.aggregation_manager = aggregation_manager
        self.queues = {}  # source_id -> queue mapping
        self.processors = {}  # source_id -> processor thread mapping
        self.running = False
        self.lock = threading.Lock()
        
        # Metrics tracking
        self.processed_logs_count = {}  # source_id -> count mapping
        self.last_processed_timestamp = {}  # source_id -> timestamp mapping
        self.metrics_lock = threading.Lock()
        
        # Log immediate template creation for new sources
        if aggregation_manager:
            logger.info("Aggregation manager is available - will auto-create templates from first logs")
    
    def start(self):
        """Start all processor threads."""
        self.running = True
        
        sources = self.source_manager.get_sources()
        for source_id in sources:
            # Initialize metrics for each source
            with self.metrics_lock:
                if source_id not in self.processed_logs_count:
                    self.processed_logs_count[source_id] = 0
                if source_id not in self.last_processed_timestamp:
                    self.last_processed_timestamp[source_id] = None
            
            self._ensure_processor(source_id)
        
        logger.info(f"Started processor threads for {len(sources)} sources")
    
    def stop(self):
        """Stop all processor threads."""
        self.running = False
        
        # Wait for all processors to finish
        for processor_thread in self.processors.values():
            processor_thread.join(timeout=5)
        
        self.processors = {}
        self.queues = {}
        logger.info("All processor threads stopped")
    
    def get_metrics(self):
        """Get current metrics for all sources.
        
        Returns:
            dict: Dictionary with processed_logs_count and last_processed_timestamp
        """
        with self.metrics_lock:
            return {
                "processed_logs_count": self.processed_logs_count.copy(),
                "last_processed_timestamp": self.last_processed_timestamp.copy()
            }
    
    def queue_log(self, log_str, source_id):
        """Queue a log for processing.
        
        Args:
            log_str: Log string to process
            source_id: Source ID this log came from
        """
        # Ensure we have a queue and processor for this source
        self._ensure_processor(source_id)
        
        # Auto-create a template from the first log if we have an aggregation manager
        # and the queue is empty (meaning this is likely the first log)
        if hasattr(self, 'aggregation_manager') and self.aggregation_manager:
            # Check if this is the first log (empty queue)
            if source_id in self.queues and self.queues[source_id].qsize() == 0:
                # Check if we already have a template
                if source_id not in self.aggregation_manager.templates:
                    try:
                        # Use this log as the template
                        self.aggregation_manager.store_log_template(source_id, log_str)
                        logger.info(f"Auto-created log template for source {source_id} from first log")
                    except Exception as e:
                        logger.error(f"Error creating template from first log: {e}")
        
        # Add log to queue
        q = self.queues[source_id]
        q.put(log_str)
        
        # Check if we need to spawn additional processor
        qsize = q.qsize()
        current_processors = sum(1 for p_id, p_info in self.processors.items() 
                                if p_id.startswith(f"{source_id}:") and p_info.is_alive())
        
        # If queue size exceeds limit, spawn additional processor
        if qsize > DEFAULT_QUEUE_LIMIT * current_processors:
            new_id = f"{source_id}:{time.time()}"
            new_thread = threading.Thread(
                target=self._processor_worker,
                args=(new_id, source_id),
                daemon=True
            )
            with self.lock:
                self.processors[new_id] = new_thread
                new_thread.start()
            logger.info(f"Spawned additional processor for source {source_id} (queue size: {qsize})")
    
    def update_processors(self):
        """Update processors based on current source configuration."""
        with self.lock:
            # Stop all processors
            self.stop()
            
            # Start processors again with updated configuration
            self.start()
    
    def _ensure_processor(self, source_id):
        """Ensure a processor exists for the given source.
        
        Args:
            source_id: Source ID to create processor for
        """
        with self.lock:
            # Create queue if needed
            if source_id not in self.queues:
                self.queues[source_id] = queue.Queue()
            
            # Create processor thread if needed
            processor_id = f"{source_id}:main"
            if processor_id not in self.processors or not self.processors[processor_id].is_alive():
                thread = threading.Thread(
                    target=self._processor_worker,
                    args=(processor_id, source_id),
                    daemon=True
                )
                self.processors[processor_id] = thread
                thread.start()
    
    def _processor_worker(self, processor_id, source_id):
        """Worker thread for processing logs.
        
        Args:
            processor_id: Unique identifier for this processor thread
            source_id: Source ID this processor handles
        """
        logger.info(f"Starting processor {processor_id} for source {source_id}")
        last_activity_time = time.time()  # Track when we last received a log
        batch = []  # Keep batch state between iterations
        
        while self.running:
            try:
                # Get source configuration
                source = self.source_manager.get_source(source_id)
                if not source:
                    logger.error(f"Source {source_id} not found, stopping processor")
                    break
                
                # Get batch size
                batch_size = int(source.get("batch_size", 
                                           500 if source["target_type"] == "HEC" else 5000))
                
                # Check if we need to force a flush due to inactivity
                current_time = time.time()
                time_since_activity = current_time - last_activity_time
                force_flush = batch and time_since_activity >= MAX_FLUSH_INTERVAL
                
                # If we need to force flush, process the current batch
                if force_flush:
                    logger.info(f"Forced flush after {time_since_activity:.1f}s of inactivity for source {source['source_name']} ({len(batch)} logs)")
                    
                    # Apply aggregation if enabled
                    if self.aggregation_manager and batch:
                        try:
                            # Use the aggregation manager to aggregate the batch
                            original_size = len(batch)
                            batch = self.aggregation_manager.aggregate_batch(batch, source_id)
                            new_size = len(batch)
                            
                            if original_size != new_size:
                                logger.info(f"Aggregated batch from {original_size} to {new_size} logs for source {source['source_name']}")
                        except Exception as e:
                            logger.error(f"Error aggregating logs: {e}")
                            # Continue with original batch on error
                    
                    processed_batch = self._process_batch(batch, source)
                    
                    # Deliver the batch to the target
                    if source["target_type"] == "FOLDER":
                        self._deliver_to_folder(processed_batch, source)
                    elif source["target_type"] == "HEC":
                        self._deliver_to_hec(processed_batch, source)
                    
                    # Update metrics for processed logs
                    with self.metrics_lock:
                        self.processed_logs_count[source_id] = self.processed_logs_count.get(source_id, 0) + len(batch)
                        self.last_processed_timestamp[source_id] = datetime.now()
                    
                    # Clear the batch and reset activity time
                    batch = []
                    last_activity_time = current_time
                    continue  # Skip to next iteration
                
                # Try to collect more logs for the batch
                try:
                    # Determine wait time:
                    # - If batch empty, wait longer (1 second)
                    # - If approaching flush interval, wait less time
                    # - Otherwise, use standard short wait
                    if not batch:
                        wait_time = 1.0  # Longer wait when no logs yet
                    elif MAX_FLUSH_INTERVAL - time_since_activity < 5:
                        wait_time = 0.1  # Shorter wait when close to timeout
                    else:
                        wait_time = 0.5  # Standard wait
                    
                    # Get a log if available
                    log_str = self.queues[source_id].get(timeout=wait_time)
                    batch.append(log_str)
                    self.queues[source_id].task_done()
                    last_activity_time = time.time()  # Update activity timestamp
                    
                    # Try to get more logs without blocking (drain queue up to batch size)
                    while len(batch) < batch_size:
                        try:
                            log_str = self.queues[source_id].get_nowait()
                            batch.append(log_str)
                            self.queues[source_id].task_done()
                        except queue.Empty:
                            break
                    
                    # If batch is full, process it
                    if len(batch) >= batch_size:
                        # Apply aggregation if enabled
                        if self.aggregation_manager and batch:
                            try:
                                # Use the aggregation manager to aggregate the batch
                                original_size = len(batch)
                                batch = self.aggregation_manager.aggregate_batch(batch, source_id)
                                new_size = len(batch)
                                
                                if original_size != new_size:
                                    logger.info(f"Aggregated batch from {original_size} to {new_size} logs for source {source['source_name']}")
                            except Exception as e:
                                logger.error(f"Error aggregating logs: {e}")
                                # Continue with original batch on error
                        
                        processed_batch = self._process_batch(batch, source)
                        
                        # Deliver the batch to the target
                        if source["target_type"] == "FOLDER":
                            self._deliver_to_folder(processed_batch, source)
                        elif source["target_type"] == "HEC":
                            self._deliver_to_hec(processed_batch, source)
                        
                        # Update metrics for processed logs
                        with self.metrics_lock:
                            self.processed_logs_count[source_id] = self.processed_logs_count.get(source_id, 0) + len(batch)
                            self.last_processed_timestamp[source_id] = datetime.now()
                        
                        # Clear the batch and reset activity time
                        batch = []
                        last_activity_time = time.time()
                
                except queue.Empty:
                    # No log available within timeout, continue waiting
                    pass
            
            except Exception as e:
                logger.error(f"Error in processor {processor_id}: {e}")
                time.sleep(1)  # Prevent tight loop on repeated errors
        
        # Ensure any remaining logs are processed when stopping
        if batch and self.running:
            try:
                source = self.source_manager.get_source(source_id)
                if source:
                    # Apply aggregation if enabled
                    if self.aggregation_manager and batch:
                        try:
                            # Use the aggregation manager to aggregate the batch
                            original_size = len(batch)
                            batch = self.aggregation_manager.aggregate_batch(batch, source_id)
                            new_size = len(batch)
                            
                            if original_size != new_size:
                                logger.info(f"Aggregated batch from {original_size} to {new_size} logs for source {source['source_name']}")
                        except Exception as e:
                            logger.error(f"Error aggregating logs: {e}")
                            # Continue with original batch on error
                    
                    processed_batch = self._process_batch(batch, source)
                    
                    # Deliver the batch to the target
                    if source["target_type"] == "FOLDER":
                        self._deliver_to_folder(processed_batch, source)
                    elif source["target_type"] == "HEC":
                        self._deliver_to_hec(processed_batch, source)
                    
                    # Update metrics for processed logs
                    with self.metrics_lock:
                        self.processed_logs_count[source_id] = self.processed_logs_count.get(source_id, 0) + len(batch)
                        self.last_processed_timestamp[source_id] = datetime.now()
                    
                    logger.info(f"Processed remaining {len(batch)} logs before stopping processor {processor_id}")
            except Exception as e:
                logger.error(f"Error processing remaining logs in processor {processor_id}: {e}")
        
        logger.info(f"Processor {processor_id} stopped")
    
    def _process_batch(self, batch, source):
        """Process a batch of logs.
        
        Args:
            batch: List of log strings to process
            source: Source configuration
            
        Returns:
            List of processed log events
        """
        processed_batch = []
        current_time = int(time.time())
        source_name = source["source_name"]
        
        for log_str in batch:
            try:
                # Try to parse log as JSON
                try:
                    log_data = json.loads(log_str)
                    # Log is valid JSON, create event with parsed data
                    event = {
                        "time": current_time,
                        "event": log_data,
                        "source": source_name
                    }
                except json.JSONDecodeError:
                    # Log is not JSON, create event with string
                    event = {
                        "time": current_time,
                        "event": log_str,
                        "source": source_name
                    }
                
                processed_batch.append(event)
            except Exception as e:
                logger.error(f"Error processing log for source {source_name}: {e}")
        
        return processed_batch
    
    def _deliver_to_folder(self, batch, source):
        """Deliver a batch of logs to a folder with optional compression.
        
        Args:
            batch: List of processed log events
            source: Source configuration
        """
        if not batch:
            return
        
        try:
            # Get folder path
            folder_path = Path(source["folder_path"])
            os.makedirs(folder_path, exist_ok=True)
            
            # Generate timestamp for filename
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            
            # Check if compression is enabled for this source
            compression_enabled = source.get("compression_enabled", 
                                         DEFAULT_COMPRESSION_ENABLED)
            compression_level = source.get("compression_level", 
                                       DEFAULT_COMPRESSION_LEVEL)
            
            # Set filename based on compression
            if compression_enabled:
                filename = f"{timestamp}.json.gz"
            else:
                filename = f"{timestamp}.json"
                
            file_path = folder_path / filename
            
            # Write logs based on compression setting
            if compression_enabled:
                # Write to compressed file
                with gzip.open(file_path, "wt", encoding="utf-8", 
                          compresslevel=compression_level) as f:
                    for event in batch:
                        json.dump(event, f)
                        f.write("\n")
            else:
                # Write to regular file
                with open(file_path, "w", encoding="utf-8") as f:
                    for event in batch:
                        json.dump(event, f)
                        f.write("\n")
            
            # Update index file
            index_path = folder_path / "index.json"
            index_data = {}
            
            if index_path.exists():
                try:
                    with open(index_path, "r") as f:
                        index_data = json.load(f)
                except json.JSONDecodeError:
                    # Index file is corrupt, start fresh
                    index_data = {"files": []}
            else:
                index_data = {"files": []}
            
            # Add file to index
            file_info = {
                "filename": filename,
                "timestamp": timestamp,
                "count": len(batch),
            }
            
            # Add compression info if enabled
            if compression_enabled:
                file_info["compressed"] = True
                file_info["compression_level"] = compression_level
            
            index_data["files"].append(file_info)
            
            # Write updated index
            with open(index_path, "w") as f:
                json.dump(index_data, f, indent=2)
            
            compression_status = "compressed " if compression_enabled else ""
            logger.info(f"Delivered {len(batch)} logs to {compression_status}file for source {source['source_name']}")
        
        except Exception as e:
            logger.error(f"Error delivering logs to folder for source {source['source_name']}: {e}")
    
    def _deliver_to_hec(self, batch, source):
        """Deliver a batch of logs to HEC.
        
        Args:
            batch: List of processed log events
            source: Source configuration
        """
        if not batch:
            return
        
        try:
            # Get HEC URL and token
            url = source["hec_url"]
            token = source["hec_token"]
            
            # Prepare data
            data = "\n".join(json.dumps(event) for event in batch)
            
            # Send request
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "text/plain; charset=utf-8"
            }
            
            response = requests.post(
                url,
                data=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Delivered {len(batch)} logs to HEC for source {source['source_name']}")
            else:
                logger.error(f"Error delivering logs to HEC for source {source['source_name']}: "
                            f"HTTP {response.status_code}, {response.text}")
        
        except Exception as e:
            logger.error(f"Error delivering logs to HEC for source {source['source_name']}: {e}")
