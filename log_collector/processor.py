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
from datetime import datetime
from pathlib import Path

from log_collector.config import (
    logger,
    DEFAULT_QUEUE_LIMIT,
)

class ProcessorManager:
    """Manages log processing queues and worker threads."""
    
    def __init__(self, source_manager):
        """Initialize the processor manager.
        
        Args:
            source_manager: Instance of SourceManager to access source configs
        """
        self.source_manager = source_manager
        self.queues = {}  # source_id -> queue mapping
        self.processors = {}  # source_id -> processor thread mapping
        self.running = False
        self.lock = threading.Lock()
        
        # Add stats tracking
        self.stats = {}  # source_id -> stats mapping
    
    def start(self):
        """Start all processor threads."""
        self.running = True
        
        sources = self.source_manager.get_sources()
        for source_id in sources:
            self._ensure_processor(source_id)
            # Initialize stats for this source
            self.stats[source_id] = {
                "processed_logs": 0,
                "last_batch_time": time.time()
            }
        
        logger.info(f"Started processor threads for {len(sources)} sources")
    
    def stop(self):
        """Stop all processor threads."""
        self.running = False
        
        # Wait for all processors to finish
        for processor_thread in self.processors.values():
            processor_thread.join(timeout=5)
        
        self.processors = {}
        
        # Process any remaining logs in queues before clearing them
        self._process_remaining_logs()
        
        self.queues = {}
        logger.info("All processor threads stopped")
    
    def _process_remaining_logs(self):
        """Process any remaining logs in queues before shutting down."""
        for source_id, q in self.queues.items():
            if q.qsize() > 0:
                source = self.source_manager.get_source(source_id)
                if not source:
                    continue
                
                # Collect all remaining logs
                batch = []
                try:
                    while True:
                        log_str = q.get_nowait()
                        batch.append(log_str)
                        q.task_done()
                except queue.Empty:
                    pass
                
                if batch:
                    # Process and deliver the batch
                    processed_batch = self._process_batch(batch, source)
                    
                    if source["target_type"] == "FOLDER":
                        self._deliver_to_folder(processed_batch, source)
                    elif source["target_type"] == "HEC":
                        self._deliver_to_hec(processed_batch, source)
                    
                    logger.info(f"Processed {len(batch)} remaining logs for source {source['source_name']} during shutdown")
    
    def queue_log(self, log_str, source_id):
        """Queue a log for processing.
        
        Args:
            log_str: Log string to process
            source_id: Source ID this log came from
        """
        # Ensure we have a queue and processor for this source
        self._ensure_processor(source_id)
        
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
            
            # Initialize stats if needed
            if source_id not in self.stats:
                self.stats[source_id] = {
                    "processed_logs": 0,
                    "last_batch_time": time.time()
                }
    
    def _processor_worker(self, processor_id, source_id):
        """Worker thread for processing logs.
        
        Args:
            processor_id: Unique identifier for this processor thread
            source_id: Source ID this processor handles
        """
        logger.info(f"Starting processor {processor_id} for source {source_id}")
        
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
                
                # Get the current time to check for forced processing
                current_time = time.time()
                
                # Check if we need to force processing due to time
                force_processing = False
                if source_id in self.stats:
                    last_batch_time = self.stats[source_id]["last_batch_time"]
                    # Force processing after 60 seconds since last batch
                    if current_time - last_batch_time > 60:
                        force_processing = True
                
                # Collect logs into batch
                batch = []
                start_time = time.time()
                timeout = 0.1  # 100ms timeout for batch collection
                
                while len(batch) < batch_size and time.time() - start_time < timeout:
                    try:
                        log_str = self.queues[source_id].get(timeout=timeout - (time.time() - start_time))
                        batch.append(log_str)
                        self.queues[source_id].task_done()
                    except queue.Empty:
                        break
                
                # If batch is empty and no force processing, wait a bit and try again
                if not batch and not force_processing:
                    time.sleep(0.1)
                    continue
                
                # If force processing and queue is not empty, get all available logs
                if force_processing and not batch:
                    try:
                        while True:
                            log_str = self.queues[source_id].get_nowait()
                            batch.append(log_str)
                            self.queues[source_id].task_done()
                    except queue.Empty:
                        pass
                
                # If we still have no logs, continue
                if not batch:
                    # Update last batch time to prevent continuous forced processing
                    if force_processing:
                        with self.lock:
                            if source_id in self.stats:
                                self.stats[source_id]["last_batch_time"] = current_time
                    continue
                
                # Process the batch
                processed_batch = self._process_batch(batch, source)
                
                # Deliver the batch to the target
                if source["target_type"] == "FOLDER":
                    self._deliver_to_folder(processed_batch, source)
                elif source["target_type"] == "HEC":
                    self._deliver_to_hec(processed_batch, source)
                
                # Update stats for this source
                with self.lock:
                    if source_id in self.stats:
                        self.stats[source_id]["processed_logs"] += len(batch)
                        self.stats[source_id]["last_batch_time"] = current_time
            
            except Exception as e:
                logger.error(f"Error in processor {processor_id}: {e}")
                time.sleep(1)  # Prevent tight loop on repeated errors
        
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
        """Deliver a batch of logs to a folder.
        
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
            filename = f"{timestamp}.json"
            file_path = folder_path / filename
            
            # Write logs to file
            with open(file_path, "w") as f:
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
            index_data["files"].append({
                "filename": filename,
                "timestamp": timestamp,
                "count": len(batch)
            })
            
            # Write updated index
            with open(index_path, "w") as f:
                json.dump(index_data, f, indent=2)
            
            logger.info(f"Delivered {len(batch)} logs to folder for source {source['source_name']}")
        
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
    
    def get_source_stats(self, source_id):
        """Get statistics for a source.
        
        Args:
            source_id: Source ID
            
        Returns:
            dict: Source statistics
        """
        with self.lock:
            if source_id in self.stats:
                stats = self.stats[source_id].copy()
                
                # Add queue size
                if source_id in self.queues:
                    stats["queue_size"] = self.queues[source_id].qsize()
                else:
                    stats["queue_size"] = 0
                
                # Add active processors count
                stats["active_processors"] = sum(
                    1 for p_id, p_thread in self.processors.items()
                    if p_id.startswith(f"{source_id}:") and p_thread.is_alive()
                )
                
                return stats
            
            return {
                "processed_logs": 0,
                "queue_size": 0,
                "active_processors": 0,
                "last_batch_time": 0
            }
