#!/bin/bash

echo "=========================================="
echo "CPU & Memory Spike Testing for Service B"
echo "=========================================="
echo ""
echo "This script demonstrates CPU and Memory spikes in Service B"
echo "Open Grafana at http://localhost:3000 to observe:"
echo "  - B - CPU Usage (FastAPI) panel"
echo "  - B - Memory Usage panel"
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

# Get initial memory baseline
echo "Getting baseline metrics..."
BASELINE=$(curl -s http://localhost:8081/metrics | grep -E "b_memory_usage_percent" | grep -v "#" | awk '{print $2}')
echo "Baseline memory usage: ${BASELINE}%"
echo ""

echo "Phase 1: Warm-up - Small requests (establish baseline) - 5 seconds"
echo "------------------------------------------------------"
for i in {1..5}; do
    echo -n "Normal request $i... "
    curl -s "http://localhost:8080/process?device_id=test-$i&ms=50" > /dev/null 2>&1
    echo "done"
    sleep 1
done

echo ""
echo "Phase 2: Small memory & CPU spike - 3 seconds"
echo "------------------------------------------------------"
echo "Processing 500 records with intensity 0.5 (light load)..."
curl -X POST "http://localhost:8080/batch_process?size=500&intensity=0.5" 2>/dev/null | jq -r '.status + " - " + (.processing_time_ms | tostring) + "ms"'
sleep 3

echo ""
echo "Phase 3: Medium memory & CPU spike - 5 seconds"
echo "------------------------------------------------------"
echo "Processing 2000 records with intensity 1.0 (normal load)..."
time curl -X POST "http://localhost:8080/batch_process?size=2000&intensity=1.0" 2>/dev/null | jq -r '.status + " - " + (.processing_time_ms | tostring) + "ms"'
sleep 3

echo ""
echo "Phase 4: Large memory & CPU spike (parallel) - 10 seconds"
echo "------------------------------------------------------"
echo "Starting 2 parallel large batch processes..."
echo "  - Batch 1: 3000 records, intensity 1.2"
echo "  - Batch 2: 2500 records, intensity 1.0"

# Start parallel batch processing
curl -s -X POST "http://localhost:8080/batch_process?size=3000&intensity=1.2" > /tmp/batch1.json 2>&1 &
PID1=$!
curl -s -X POST "http://localhost:8080/batch_process?size=2500&intensity=1.0" > /tmp/batch2.json 2>&1 &
PID2=$!

# Monitor while processing
echo "Processing in parallel..."
for i in {1..15}; do
    MEM=$(curl -s http://localhost:8081/metrics | grep -E "b_memory_usage_percent" | grep -v "#" | awk '{print $2}')
    CPU=$(curl -s http://localhost:8081/metrics | grep -E "b_cpu_usage_percent" | grep -v "#" | awk '{print $2}')
    echo "  [$i] CPU: ${CPU}% | Memory: ${MEM}%"
    sleep 1
done

# Wait for parallel processes to complete
wait $PID1
wait $PID2

echo ""
echo "Batch processing results:"
cat /tmp/batch1.json | jq -r '"  Batch 1: " + .status + " - " + (.records_processed | tostring) + " records"' 2>/dev/null || echo "  Batch 1: Still processing or failed"
cat /tmp/batch2.json | jq -r '"  Batch 2: " + .status + " - " + (.records_processed | tostring) + " records"' 2>/dev/null || echo "  Batch 2: Still processing or failed"

echo ""
echo "Phase 5: Maximum stress test (single large batch) - 15 seconds"
echo "------------------------------------------------------"
echo "Processing 5000 records with intensity 1.5 (high load)..."
echo "This will create significant memory and CPU spikes..."

# Start the process in background
curl -s -X POST "http://localhost:8080/batch_process?size=5000&intensity=1.5" > /tmp/batch_max.json 2>&1 &
MAX_PID=$!

# Monitor during processing
echo "Monitoring system resources during processing:"
for i in {1..20}; do
    MEM=$(curl -s http://localhost:8081/metrics | grep -E "b_memory_usage_percent" | grep -v "#" | awk '{print $2}')
    CPU=$(curl -s http://localhost:8081/metrics | grep -E "b_cpu_usage_percent" | grep -v "#" | awk '{print $2}')
    BATCH=$(curl -s http://localhost:8081/metrics | grep -E "b_batch_processing" | grep -v "#" | awk '{print $2}')
    
    if [ "$BATCH" = "1.0" ]; then
        STATUS="🔥 PROCESSING"
    else
        STATUS="⏸  IDLE"
    fi
    
    printf "  [%2d] CPU: %6.1f%% | Memory: %5.2f%% | Status: %s\n" $i $CPU $MEM "$STATUS"
    sleep 1
done

wait $MAX_PID
echo ""
cat /tmp/batch_max.json | jq -r '"Result: " + .status + " - Processed " + (.records_processed | tostring) + " records"' 2>/dev/null || echo "Result: Processing completed or failed"

echo ""
echo "Phase 6: Recovery monitoring - 10 seconds"
echo "------------------------------------------------------"
echo "Monitoring resource recovery..."
for i in {1..10}; do
    MEM=$(curl -s http://localhost:8081/metrics | grep -E "b_memory_usage_percent" | grep -v "#" | awk '{print $2}')
    CPU=$(curl -s http://localhost:8081/metrics | grep -E "b_cpu_usage_percent" | grep -v "#" | awk '{print $2}')
    echo "  [$i] CPU: ${CPU}% | Memory: ${MEM}%"
    
    # Send normal request to maintain activity
    curl -s "http://localhost:8080/process?device_id=recovery-$i&ms=50" > /dev/null 2>&1
    sleep 1
done

# Final metrics
echo ""
echo "=========================================="
echo "Test completed!"
echo ""
echo "Final metrics:"
FINAL_MEM=$(curl -s http://localhost:8081/metrics | grep -E "b_memory_usage_percent" | grep -v "#" | awk '{print $2}')
FINAL_CPU=$(curl -s http://localhost:8081/metrics | grep -E "b_cpu_usage_percent" | grep -v "#" | awk '{print $2}')
BATCH_COUNT=$(curl -s http://localhost:8081/metrics | grep -E "b_batch_size_count" | grep -v "#" | awk '{print $2}')

echo "  Baseline memory: ${BASELINE}%"
echo "  Final memory: ${FINAL_MEM}%"
echo "  Final CPU: ${FINAL_CPU}%"
echo "  Total batches processed: ${BATCH_COUNT}"
echo ""
echo "Check Grafana dashboards to see:"
echo "1. CPU spikes during batch processing (up to 100%+)"
echo "2. Memory growth during data loading and processing"
echo "3. Resource recovery after processing completion"
echo "4. Correlation between batch processing indicator and resource usage"
echo "=========================================="

# Cleanup
rm -f /tmp/batch*.json