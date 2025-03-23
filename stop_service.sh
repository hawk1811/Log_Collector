#!/bin/bash
echo "Stopping LogCollector service..."
./LogCollector --service stop
echo ""
echo "Service stop command sent. Check logs for details."
read -p "Press Enter to continue..."
