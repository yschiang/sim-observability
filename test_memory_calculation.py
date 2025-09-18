#!/usr/bin/env python3

import requests
import time
import json

def test_memory_before_after():
    print("=== Memory Test Script ===")
    
    # Get baseline
    baseline = requests.get("http://localhost:8081/metrics").text
    baseline_mem = [line for line in baseline.split('\n') if line.startswith('b_memory_usage_percent')]
    print(f"Baseline: {baseline_mem[0] if baseline_mem else 'Not found'}")
    
    print("\nTriggering aggressive memory allocation...")
    
    # Trigger large batch processing
    response = requests.post("http://localhost:8080/batch_process", params={
        'size': 8000,
        'intensity': 3.0
    })
    
    print(f"Batch result: {response.json()}")
    
    # Wait a bit and check memory
    time.sleep(2)
    
    after = requests.get("http://localhost:8081/metrics").text
    after_mem = [line for line in after.split('\n') if line.startswith('b_memory_usage_percent')]
    print(f"After processing: {after_mem[0] if after_mem else 'Not found'}")
    
    # Extract values for comparison
    if baseline_mem and after_mem:
        baseline_val = float(baseline_mem[0].split()[1])
        after_val = float(after_mem[0].split()[1])
        print(f"\nMemory change: {baseline_val:.2f}% → {after_val:.2f}% (Δ{after_val-baseline_val:+.2f}%)")
        
        # This should show a significant change if calculated against 256MB
        if after_val > baseline_val * 2:  # At least 2x increase
            print("✅ Significant memory increase detected!")
        else:
            print("❌ Memory increase is too small - likely using system memory as denominator")
    
    print("\n=== Docker Stats Comparison ===")
    import subprocess
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "sim-observability-full-bundle-b-1", "--format", "{{.MemUsage}} ({{.MemPerc}})"],
        capture_output=True, text=True
    )
    print(f"Docker stats: {result.stdout.strip()}")

if __name__ == "__main__":
    test_memory_before_after()