"""
Listener module for receiving logs from various sources.
Manages TCP and UDP server sockets for log ingestion.
"""
import json
import socket
import threading
import queue
import time
from collections import defaultdict

from log_collector.config import logger

class LogListener:
    """Manages network listeners for log collection."""
    
    def __init__(self, source_manager, processor_manager):
        """Initialize the log listener.
        
        Args:
            source_manager: Instance of SourceManager to access source configs
            processor_manager: Instance of ProcessorManager to queue logs for processing
        """
        self.source_manager = source_manager
        self.processor_manager = processor_manager
        self.listeners = {}  # port -> listener thread mapping
        self.running = False
        self.lock = threading.Lock()
    
    def start(self):
        """Start all configured listeners."""
        self.running = True
        
        # Group sources by port
        port_map = defaultdict(list)
        for source_id, source in self.source_manager.get_sources().items():
            port = int(source["listener_port"])
            port_map[port].append((source_id, source))
        
        # Start a listener for each port
        for port, sources in port_map.items():
            self._start_listener(port, sources)
        
        logger.info(f"Started {len(port_map)} listener(s)")
    
    def stop(self):
        """Stop all listeners."""
        self.running = False
        for listener_thread in self.listeners.values():
            listener_thread.join(timeout=5)
        self.listeners = {}
        logger.info("All listeners stopped")
    
    def update_listeners(self):
        """Update listeners based on current source configuration."""
        with self.lock:
            # Stop all listeners
            self.stop()
            
            # Start listeners again with updated configuration
            self.start()
    
    def _start_listener(self, port, sources):
        """Start a listener for a specific port.
        
        Args:
            port: Port number to listen on
            sources: List of (source_id, source_config) tuples sharing this port
        """
        # Determine if we need TCP or UDP or both
        needs_tcp = any(source[1]["protocol"] == "TCP" for source in sources)
        needs_udp = any(source[1]["protocol"] == "UDP" for source in sources)
        
        # Start appropriate listener threads
        if needs_udp:
            udp_thread = threading.Thread(
                target=self._udp_listener,
                args=(port, sources),
                daemon=True
            )
            udp_thread.start()
            self.listeners[f"UDP:{port}"] = udp_thread
        
        if needs_tcp:
            tcp_thread = threading.Thread(
                target=self._tcp_listener,
                args=(port, sources),
                daemon=True
            )
            tcp_thread.start()
            self.listeners[f"TCP:{port}"] = tcp_thread
    
    def _udp_listener(self, port, sources):
        """UDP listener implementation.
        
        Args:
            port: Port number to listen on
            sources: List of (source_id, source_config) tuples for this port
        """
        # Create source IP to source_id mapping for quick lookup
        ip_map = {source[1]["source_ip"]: source[0] for source in sources}
        
        # Set up UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(("0.0.0.0", port))
            logger.info(f"UDP listener started on port {port}")
            
            # Set socket to non-blocking with timeout
            sock.settimeout(0.5)
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(65535)  # Max UDP packet size
                    source_ip = addr[0]
                    
                    # Check if source IP is allowed
                    if source_ip in ip_map:
                        source_id = ip_map[source_ip]
                        self._process_log(data, source_id)
                    else:
                        logger.warning(f"Received UDP log from unauthorized IP: {source_ip}")
                
                except socket.timeout:
                    # This is normal - just retry
                    continue
                except Exception as e:
                    logger.error(f"Error in UDP listener on port {port}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to start UDP listener on port {port}: {e}")
        finally:
            sock.close()
    
    def _tcp_listener(self, port, sources):
        """TCP listener implementation.
        
        Args:
            port: Port number to listen on
            sources: List of (source_id, source_config) tuples for this port
        """
        # Create source IP to source_id mapping for quick lookup
        ip_map = {source[1]["source_ip"]: source[0] for source in sources}
        
        # Set up TCP socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind(("0.0.0.0", port))
            server_socket.listen(5)
            server_socket.settimeout(0.5)
            logger.info(f"TCP listener started on port {port}")
            
            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    client_handler = threading.Thread(
                        target=self._handle_tcp_client,
                        args=(client_socket, addr, ip_map),
                        daemon=True
                    )
                    client_handler.start()
                except socket.timeout:
                    # This is normal - just retry
                    continue
                except Exception as e:
                    logger.error(f"Error accepting TCP connection on port {port}: {e}")
        
        except Exception as e:
            logger.error(f"Failed to start TCP listener on port {port}: {e}")
        finally:
            server_socket.close()
    
    def _handle_tcp_client(self, client_socket, addr, ip_map):
        """Handle TCP client connection.
        
        Args:
            client_socket: Connected client socket
            addr: Client address tuple (ip, port)
            ip_map: Mapping of source IPs to source IDs
        """
        source_ip = addr[0]
        
        # Check if source IP is allowed
        if source_ip not in ip_map:
            logger.warning(f"TCP connection from unauthorized IP: {source_ip}")
            client_socket.close()
            return
        
        source_id = ip_map[source_ip]
        client_socket.settimeout(30)  # 30-second timeout for inactivity
        
        try:
            buffer = b""
            while self.running:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break  # Connection closed by client
                    
                    buffer += data
                    
                    # Process complete logs (assuming newline delimiter)
                    while b"\n" in buffer:
                        log, buffer = buffer.split(b"\n", 1)
                        if log:  # Skip empty lines
                            self._process_log(log, source_id)
                
                except socket.timeout:
                    # Connection inactive
                    break
                except Exception as e:
                    logger.error(f"Error receiving TCP data: {e}")
                    break
            
            # Process any remaining data in buffer
            if buffer:
                self._process_log(buffer, source_id)
        
        finally:
            client_socket.close()
    
    def _process_log(self, data, source_id):
        """Process a received log message.
        
        Args:
            data: Raw log data (bytes)
            source_id: Source ID this log came from
        """
        try:
            # Try to decode as UTF-8
            log_str = data.decode("utf-8")
            
            # Queue the log for processing
            self.processor_manager.queue_log(log_str, source_id)
        
        except UnicodeDecodeError:
            # If UTF-8 decoding fails, use latin-1 which can decode any byte sequence
            log_str = data.decode("latin-1")
            self.processor_manager.queue_log(log_str, source_id)
        
        except Exception as e:
            logger.error(f"Error processing log for source {source_id}: {e}")