#!/bin/bash
set -e

echo "=== Observability Simulation Test Suite ==="
echo "Running all 12 test cases in sequence..."
echo ""

# Check if services are running
echo "🔍 Checking services..."
curl -f http://localhost:8080/health > /dev/null || (echo "❌ Service B not ready"; exit 1)
curl -f http://localhost:8002/health > /dev/null || (echo "❌ Fast device not ready"; exit 1) 
curl -f http://localhost:8003/health > /dev/null || (echo "❌ Slow device not ready"; exit 1)
echo "✅ All services ready"
echo ""

# Phase 1: Basic Functionality (30s each)
echo "🧪 Phase 1: Basic Functionality Tests"
for i in {1..4}; do
    echo "Running Test Case $i..."
    python3 test/simple-load.py --testcase $i
    echo ""
done

# Phase 2: Load Testing (60s each)
echo "⚡ Phase 2: Load Testing"
for i in {5..7}; do
    echo "Running Test Case $i..."
    python3 test/simple-load.py --testcase $i
    echo ""
done

# Phase 3: Retry Storm Testing (60s each)
echo "🌪️  Phase 3: Retry Storm Testing"
for i in {8..10}; do
    echo "Running Test Case $i..."
    python3 test/simple-load.py --testcase $i
    echo ""
done

# Phase 4: Extended Stability (300s each) - Optional
read -p "🕐 Run Phase 4 Extended Tests (10+ minutes)? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🏃 Phase 4: Extended Stability Testing"
    for i in {11..12}; do
        echo "Running Test Case $i..."
        python3 test/simple-load.py --testcase $i
        echo ""
    done
else
    echo "⏭️  Skipping Phase 4 Extended Tests"
fi

echo "🎉 Test suite completed!"
echo ""
echo "📊 Next steps:"
echo "- Check Grafana dashboards: http://localhost:3001"
echo "- Review Prometheus metrics: http://localhost:9090"
echo "- Analyze results in test output above"