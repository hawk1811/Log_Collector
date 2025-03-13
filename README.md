# Log Collector

A high-performance log collection and processing system capable of handling up to 20,000 events per second (EPS). Log Collector can receive logs via TCP or UDP, process them, and forward them to either a file system folder or a HTTP Event Collector (HEC) endpoint.

## Features

- **High Throughput**: Process up to 20,000 EPS with efficient resource utilization
- **Multiple Sources**: Configure multiple log sources with independent processing
- **Flexible Input**: Support for both TCP and UDP protocols
- **Dynamic Scaling**: Automatically scales processing threads based on queue size
- **Dual Output Options**: Send logs to filesystem or HEC endpoints
- **JSON Parsing**: Automatically detects and parses JSON-formatted logs
- **Health Monitoring**: Integrated health checks and performance monitoring
- **User-Friendly CLI**: Interactive command-line interface for easy management

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
git clone https://github.com/logcollector/log_collector.git
cd log_collector
pip install -e .
```

## Quick Start

Start the application with the CLI interface:

```bash
log_collector
```

Or run without the interactive interface (for service mode):

```bash
log_collector --no-interactive
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
     - For Folder: Folder path and batch size
     - For HEC: HEC URL, token, and batch size

### Managing Sources

Select option 2 from the main menu to:
- View all configured sources
- Edit source settings
- Delete sources

### Health Check Configuration

Select option 3 from the main menu to configure system health monitoring:
- Set HEC URL and token for health data
- Set monitoring interval (default: 60 seconds)
- Start or stop health monitoring

## Architecture

The Log Collector system consists of the following main components:

- **Source Manager**: Handles source configuration and validation
- **Listener**: Receives logs from various sources via TCP/UDP
- **Processor**: Processes logs and delivers them to targets
- **Health Check**: Monitors system and source health

Each source has two dedicated threads:
1. A listener thread that receives logs
2. A processor thread that processes and delivers logs

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
- Adjust these values based on your specific requirements and hardware capabilities

## Requirements

See `requirements.txt` for detailed dependencies.

## License

MIT License

## Support

For issues and feature requests, please open an issue on the GitHub repository.
