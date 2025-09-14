#!/bin/bash
set -e

echo "=== Quick Test Suite (Phase 1 Only) ==="
echo "Running basic functionality tests (4 cases, ~2 minutes total)"
echo ""

# Check services
echo "🔍 Checking services..."
curl -f http://localhost:8080/health > /dev/null || (echo "❌ Service B not ready"; exit 1)
echo "✅ Services ready"
echo ""

# Run Phase 1 only (30s each)
echo "🧪 Running basic functionality tests..."
for i in {1..4}; do
    echo "Test Case $i:"
    python3 test/simple-load.py --testcase $i
    echo ""
done

echo "🎉 Quick test completed!"
echo "📊 Check Grafana: http://localhost:3001"