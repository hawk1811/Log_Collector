# Log Collector

A high-performance log collection and processing system capable of handling up to 20,000 events per second (EPS) with efficient in-memory processing. Log Collector can receive logs via TCP or UDP, process them using customizable rules, and forward them to either a file system folder or a HTTP Event Collector (HEC) endpoint.

![Log Collector Dashboard Screenshot](screenshots/dashboard.png)

## Features

### High Performance

- **In-Memory Processing**: All log processing occurs in memory for maximum throughput
- **20,000+ EPS Capacity**: Handles over 20,000 events per second with minimal resource utilization
- **Dynamic Scaling**: Automatically spawns additional processing threads based on queue size
- **Non-Blocking I/O**: Optimized for continuous operation even under heavy load

### Flexible Input

- **Multiple Sources**: Configure unlimited log sources with independent processing
- **Protocol Support**: Receive logs via both TCP and UDP protocols
- **Port Sharing**: Multiple sources can share the same listening port with IP-based filtering
- **JSON Parsing**: Automatically detects and parses JSON-formatted logs

### Advanced Processing

- **Log Aggregation**: Reduce log volume with customizable aggregation rules
- **Field Extraction**: Automatically extract fields from structured and unstructured logs
- **Filtering Rules**: Configure rules to filter out unwanted log events
- **Template Learning**: Automatically learns log structure from initial events

### Storage Options

- **Dual Output Options**: Send logs to filesystem or HEC endpoints
- **High Compression**: Enable GZIP compression for efficient storage
- **Configurable Batching**: Optimize performance with customizable batch sizes
- **Network Share Support**: Store logs directly to network shares for centralized collection

### Management and Security

- **User-Friendly CLI**: Interactive command-line interface for easy management
- **Authentication**: Secure password-based authentication system
- **Health Monitoring**: Integrated health checks and performance monitoring
- **Auto-Updates**: Built-in update checking and application management

## Dashboard View

![Status Dashboard Screenshot](screenshots/status_dash.png)

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Installation Steps

1. Install from PyPI:

```bash
pip install log-collector
```

2. Or install from source:

```bash
git clone https://github.com/thehawk1811/Log_Collector.git
cd log_collector
pip install -e .
```

## Quick Start

Start the application with the CLI interface:

```bash
log_collector
```

Default username and password:

```bash
user: admin
pass: password
```

Run without the interactive interface (for service mode):

```bash
log_collector --no-interactive
```

Run as a background daemon (detached from terminal):

```bash
log_collector --no-interactive --daemon
```

You can also specify a PID file location:

```bash
log_collector --no-interactive --daemon --pid-file=/var/run/log_collector.pid
```

## Configuration

### Adding a Source

1. Start the Log Collector CLI
2. Select option 1 to add a new source
3. Enter the required information:
   - Source Name: A descriptive name for the source
   - Source IP: The IP address from which logs will be received
   - Listener Port: The port to listen on
   - Protocol: UDP (default) or TCP
   - Target Type: Folder or HEC
   - Target-specific settings:
     - For Folder: Folder path, batch size, and compression options
     - For HEC: HEC URL, token, and batch size

![Add Source Screenshot](screenshots/add_source.png)

### Managing Sources

Select option 2 from the main menu to:
- View all configured sources
- Edit source settings
- Delete sources
- Manage aggregation rules
- Configure filter rules

### Aggregation Rules

Aggregation rules allow you to reduce log volume by combining similar log events:

1. Select "Manage Aggregation Rules" from the source management menu
2. Create a new rule by selecting fields that identify similar logs
3. The system will automatically combine logs that match on these fields

![Aggregation Rules Screenshot](screenshots/aggregation.png)

### Filter Rules

Filter rules let you exclude unwanted logs from processing:

1. Select "Manage Filter Rules" from the source management menu
2. Create filters based on field values
3. Logs matching these filters will be excluded from processing

![Filter Rules Screenshot](screenshots/filters.png)

## Architecture

The Log Collector system consists of the following main components:

- **Source Manager**: Handles source configuration and validation
- **Listener**: Receives logs from various sources via TCP/UDP
- **Processor**: Processes logs and delivers them to targets
- **Aggregation Manager**: Manages log templates and aggregation rules
- **Filter Manager**: Applies filtering rules to incoming logs
- **Health Check**: Monitors system and source health

Each source has dedicated threads:
1. A listener thread that receives logs
2. One or more processor threads that process and deliver logs

Additional processor threads are automatically spawned when the queue size exceeds 10,000 logs.

## Log Format

Logs are processed into the following JSON format:

```json
{
  "time": 1647586245,
  "event": "Original log string or parsed JSON object",
  "source": "source_name"
}
```

If the incoming log is a valid JSON object, it's parsed and included as the event value. Otherwise, the raw string is used.

## Health Monitoring

The health monitoring feature collects the following data:
- CPU usage and load
- Memory usage
- Disk usage
- Network I/O
- Source-specific metrics (queue size, active processors)

This data is sent to a configured HEC endpoint at regular intervals.

## Performance Tuning

- Batch sizes can be configured per source:
  - Default for HEC targets: 500 logs per batch
  - Default for Folder targets: 5000 logs per batch
- Queue limits trigger additional processor threads (default: 10,000 logs)
- Compression level is configurable (1-9, with 9 being highest compression)
- Adjust these values based on your specific requirements and hardware capabilities

## Requirements

See `requirements.txt` for detailed dependencies.

## License

MIT License

## Support

For issues and feature requests, please open an issue on the GitHub repository.
