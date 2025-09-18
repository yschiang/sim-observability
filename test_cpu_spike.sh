#!/bin/bash

echo "=========================================="
echo "CPU Spike Testing Script for Service B"
echo "=========================================="
echo ""
echo "This script will demonstrate CPU spikes in Service B"
echo "Open Grafana at http://localhost:3000 to observe:"
echo "  - B - CPU Usage (Python) panel"
echo "  - B - Memory Usage (Python) panel"
echo ""

# Check if Service B is running
echo "Checking Service B health..."
curl -s http://localhost:8080/health > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Service B is not running. Please start with: docker compose --profile python up -d"
    exit 1
fi
echo "Service B is healthy!"
echo ""

echo "Phase 1: Normal requests (no CPU spike) - 10 seconds"
echo "------------------------------------------------------"
for i in {1..10}; do
    echo -n "Normal request $i... "
    curl -s "http://localhost:8080/process?device_id=test-$i&ms=100" > /dev/null 2>&1
    echo "done"
    sleep 1
done

echo ""
echo "Phase 2: Small batch processing (minor CPU spike) - 5 seconds"  
echo "------------------------------------------------------"
for i in {1..5}; do
    echo -n "Small batch $i (100 records)... "
    curl -s -X POST "http://localhost:8080/batch_process?size=100&intensity=0.5" > /dev/null 2>&1
    echo "done"
    sleep 1
done

echo ""
echo "Phase 3: Normal requests (CPU recovery) - 5 seconds"
echo "------------------------------------------------------"
for i in {1..5}; do
    echo -n "Normal request $i... "
    curl -s "http://localhost:8080/process?device_id=test-$i&ms=50" > /dev/null 2>&1
    echo "done"
    sleep 1
done

echo ""
echo "Phase 4: Large batch processing (major CPU spike) - 3 parallel batches"
echo "------------------------------------------------------"
echo "Starting 3 parallel batch processes..."
for i in {1..3}; do
    echo "  - Batch $i (1000 records, intensity 1.0)"
    curl -s -X POST "http://localhost:8080/batch_process?size=1000&intensity=1.0" > /dev/null 2>&1 &
done

echo "Waiting for batch processing to complete..."
wait

echo ""
echo "Phase 5: Recovery monitoring - 10 seconds"
echo "------------------------------------------------------"
for i in {1..10}; do
    echo -n "Normal request $i... "
    curl -s "http://localhost:8080/process?device_id=test-$i&ms=50" > /dev/null 2>&1
    echo "done"
    sleep 1
done

echo ""
echo "=========================================="
echo "Test completed!"
echo ""
echo "Check Grafana dashboards to see:"
echo "1. CPU spikes during batch processing phases"
echo "2. Memory usage changes"
echo "3. Batch processing indicator (purple bars)"
echo "=========================================="