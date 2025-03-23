#!/bin/bash
echo "Starting LogCollector service..."
./LogCollector --service start
echo ""
echo "Service startup initiated. Check logs for details."
read -p "Press Enter to continue..."
