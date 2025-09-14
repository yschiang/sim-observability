#!/usr/bin/env python3
"""Simple load testing tool for baseline scenario"""

import asyncio
import aiohttp
import time
import json
from typing import Dict, List
import argparse

class LoadTester:
    def __init__(self, base_url: str, concurrent_requests: int = 10):
        self.base_url = base_url
        self.concurrent_requests = concurrent_requests
        self.results = []
        
    async def make_request(self, session: aiohttp.ClientSession, device_id: str, ms: int = 3000, mode: str = "normal"):
        start_time = time.time()
        try:
            url = f"{self.base_url}/process?device_id={device_id}&ms={ms}&mode={mode}"
            async with session.get(url) as response:
                end_time = time.time()
                content = await response.text()
                return {
                    "status": response.status,
                    "latency_ms": (end_time - start_time) * 1000,
                    "device_id": device_id,
                    "mode": mode,
                    "timestamp": start_time,
                    "retry_after": response.headers.get("Retry-After"),
                    "success": 200 <= response.status < 300
                }
        except Exception as e:
            end_time = time.time()
            return {
                "status": 0,
                "latency_ms": (end_time - start_time) * 1000,
                "device_id": device_id,
                "mode": mode,
                "timestamp": start_time,
                "error": str(e),
                "success": False
            }
    
    async def run_load_test(self, duration_seconds: int = 60, devices: str = "mixed", mode: str = "normal"):
        """
        Device Types:
        - fast_only: Only dev-fast-* devices
        - slow_only: Only dev-slow-* devices  
        - mixed: Both fast and slow devices
        
        Modes:
        - normal: Only normal operations
        - error: Only error operations
        - hang: Only hang operations
        - mixed: Mix of normal/error/hang
        """
        print(f"Starting {devices}/{mode} load test for {duration_seconds}s with {self.concurrent_requests} concurrent requests")
        
        start_time = time.time()
        tasks = []
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        ) as session:
            
            while time.time() - start_time < duration_seconds:
                # Generate device_id based on device type
                if devices == "fast_only":
                    device_id = f"dev-fast-{len(tasks) % 3}"
                elif devices == "slow_only":
                    device_id = f"dev-slow-{len(tasks) % 2}"
                else:  # mixed
                    if len(tasks) % 2 == 0:
                        device_id = f"dev-fast-{len(tasks) % 3}"
                    else:
                        device_id = f"dev-slow-{len(tasks) % 2}"
                
                # Generate operation mode
                ms = 3000
                if mode == "normal":
                    req_mode = "normal"
                elif mode == "error":
                    req_mode = "error"
                elif mode == "hang":
                    req_mode = "hang"
                else:  # mixed
                    if len(tasks) % 10 == 0:  # 10% error
                        req_mode = "error"
                    elif len(tasks) % 20 == 0:  # 5% hang
                        req_mode = "hang"
                    else:
                        req_mode = "normal"
                
                # Launch request
                task = asyncio.create_task(
                    self.make_request(session, device_id, ms, req_mode)
                )
                tasks.append(task)
                
                # Control concurrency
                if len(tasks) >= self.concurrent_requests:
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        result = await task
                        self.results.append(result)
                    tasks = list(pending)
                
                # Small delay to control request rate
                await asyncio.sleep(0.1)
            
            # Wait for remaining tasks
            if tasks:
                done, _ = await asyncio.wait(tasks)
                for task in done:
                    result = await task
                    self.results.append(result)
        
        self.print_summary()
    
    def print_summary(self):
        if not self.results:
            print("No results to analyze")
            return
            
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r["success"])
        
        # Status code distribution
        status_counts = {}
        for r in self.results:
            status = r["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Latency stats
        latencies = [r["latency_ms"] for r in self.results if r["success"]]
        if latencies:
            latencies.sort()
            p50 = latencies[int(len(latencies) * 0.5)]
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) > 10 else latencies[-1]
        else:
            p50 = p95 = p99 = 0
        
        print(f"\n=== LOAD TEST RESULTS ===")
        print(f"Total requests: {total_requests}")
        print(f"Successful requests: {successful_requests} ({successful_requests/total_requests*100:.1f}%)")
        print(f"Failed requests: {total_requests - successful_requests}")
        print(f"\nStatus code distribution:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count} ({count/total_requests*100:.1f}%)")
        print(f"\nLatency percentiles (successful requests):")
        print(f"  p50: {p50:.1f}ms")
        print(f"  p95: {p95:.1f}ms") 
        print(f"  p99: {p99:.1f}ms")
        
        # Check for retry-after headers
        retry_after_count = sum(1 for r in self.results if r.get("retry_after"))
        if retry_after_count > 0:
            print(f"\nRetry-After headers seen: {retry_after_count}")

def get_test_case(case_num: int) -> dict:
    """MECE Test Case Definitions"""
    test_cases = {
        # Phase 1: Basic Functionality (30s quick tests)
        1: {"devices": "fast_only", "mode": "normal", "concurrency": 1, "duration": 30, "desc": "Fast device basic functionality"},
        2: {"devices": "slow_only", "mode": "normal", "concurrency": 1, "duration": 30, "desc": "Slow device basic functionality"},
        3: {"devices": "mixed", "mode": "error", "concurrency": 1, "duration": 30, "desc": "Error handling test"},
        4: {"devices": "mixed", "mode": "hang", "concurrency": 1, "duration": 30, "desc": "Hang/timeout handling test"},
        
        # Phase 2: Load Testing (60s standard tests)  
        5: {"devices": "fast_only", "mode": "normal", "concurrency": 20, "duration": 60, "desc": "Fast device saturation"},
        6: {"devices": "slow_only", "mode": "normal", "concurrency": 20, "duration": 60, "desc": "Slow device saturation"},
        7: {"devices": "mixed", "mode": "normal", "concurrency": 15, "duration": 60, "desc": "Mixed device load test"},
        
        # Phase 3: Retry Storm Testing (60s)
        8: {"devices": "fast_only", "mode": "normal", "concurrency": 50, "duration": 60, "desc": "Retry storm - fast devices"},
        9: {"devices": "slow_only", "mode": "normal", "concurrency": 50, "duration": 60, "desc": "Retry storm - slow devices"},
        10: {"devices": "mixed", "mode": "normal", "concurrency": 50, "duration": 60, "desc": "Retry storm - mixed devices"},
        
        # Phase 4: Extended Stability (300s)
        11: {"devices": "mixed", "mode": "mixed", "concurrency": 20, "duration": 300, "desc": "Extended stability test"},
        12: {"devices": "mixed", "mode": "normal", "concurrency": 30, "duration": 300, "desc": "Extended load test"},
    }
    return test_cases.get(case_num, {})

async def main():
    parser = argparse.ArgumentParser(description="Load test the observability simulation")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL to test")
    parser.add_argument("--testcase", type=int, choices=range(1, 13), required=True,
                       help="Test case number (1-12)")
    
    args = parser.parse_args()
    
    test_case = get_test_case(args.testcase)
    if not test_case:
        print(f"Invalid test case: {args.testcase}")
        return
    
    print(f"=== Test Case {args.testcase}: {test_case['desc']} ===")
    print(f"Devices: {test_case['devices']}, Mode: {test_case['mode']}")
    print(f"Concurrency: {test_case['concurrency']}, Duration: {test_case['duration']}s")
    
    tester = LoadTester(args.url, test_case['concurrency'])
    await tester.run_load_test(test_case['duration'], test_case['devices'], test_case['mode'])

if __name__ == "__main__":
    asyncio.run(main())