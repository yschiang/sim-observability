# Test Guide

## 🎯 **Overview**
Comprehensive testing suite for the observability simulation with numbered test cases following MECE (Mutually Exclusive, Collectively Exhaustive) principles.

## 🏗️ **System Architecture**
```
A(curl) → B(FastAPI:8080) → C(gRPC:50051) → D-Fast(8002) / D-Slow(8003)
```

**Device Types:**
- **Fast Device** (port 8002): Normal latency (~3s)
- **Slow Device** (port 8003): 3.3x slower (~10s worst-case)

**Device Routing:**
- `dev-fast-*` → Fast device
- `dev-slow-*` → Slow device  
- Everything else → Fast device

## 📋 **Test Cases (MECE)**

### **Phase 1: Basic Functionality (30s)**
| Case | Description | Devices | Mode | Concurrency | Purpose |
|------|-------------|---------|------|-------------|---------|
| 1 | Fast device basic | fast_only | normal | 1 | Verify fast device works |
| 2 | Slow device basic | slow_only | normal | 1 | Verify slow device works |
| 3 | Error handling | mixed | error | 1 | Test error responses |
| 4 | Hang/timeout handling | mixed | hang | 1 | Test timeout behavior |

### **Phase 2: Load Testing (60s)**
| Case | Description | Devices | Mode | Concurrency | Purpose |
|------|-------------|---------|------|-------------|---------|
| 5 | Fast device saturation | fast_only | normal | 20 | C saturation with fast devices |
| 6 | Slow device saturation | slow_only | normal | 20 | C saturation with slow devices |
| 7 | Mixed device load | mixed | normal | 15 | Realistic mixed traffic |

### **Phase 3: Retry Storm Testing (60s)**
| Case | Description | Devices | Mode | Concurrency | Purpose |
|------|-------------|---------|------|-------------|---------|
| 8 | Retry storm - fast | fast_only | normal | 50 | High load on fast devices |
| 9 | Retry storm - slow | slow_only | normal | 50 | High load on slow devices |
| 10 | Retry storm - mixed | mixed | normal | 50 | **Baseline retry storm test** |

### **Phase 4: Extended Stability (300s)**
| Case | Description | Devices | Mode | Concurrency | Purpose |
|------|-------------|---------|------|-------------|---------|
| 11 | Extended stability | mixed | mixed | 20 | Long-term stability |
| 12 | Extended load | mixed | normal | 30 | Sustained high load |

## 🚀 **Quick Start**

### **Prerequisites**
```bash
# Start the simulation stack
docker compose up -d --build

# Install test dependencies  
pip3 install aiohttp
```

### **Run Individual Test Cases**
```bash
# Basic functionality
python3 test/simple-load.py --testcase 1  # Fast device basic
python3 test/simple-load.py --testcase 2  # Slow device basic

# Load testing
python3 test/simple-load.py --testcase 5  # Fast saturation 
python3 test/simple-load.py --testcase 10 # Mixed retry storm

# Extended testing
python3 test/simple-load.py --testcase 12 # Extended load test
```

### **Run Full Test Suite**
```bash
# Run all phases sequentially
./test/run-all-tests.sh
```

## 📊 **Expected Results**

### **Successful Tests (Cases 1-2, 5-7)**
- **Fast devices**: ~3s latencies, low error rates
- **Slow devices**: ~10s latencies, possible timeouts
- **Mixed load**: Combination of fast/slow response patterns

### **Error/Timeout Tests (Cases 3-4)**
- **Error mode**: High HTTP 500 rates from devices
- **Hang mode**: High HTTP 504 rates (C timeouts at ~3s)

### **Retry Storm Tests (Cases 8-10)**
- **High 429 rates**: C single semaphore saturated
- **No retry amplification**: B doesn't retry on 429/504
- **Fast failure**: System fails fast rather than queuing

## 🔍 **Observability During Tests**

### **Real-time Monitoring**
```bash
# Grafana dashboards
http://localhost:3001 → Golden Signals: B & C, C Availability

# Prometheus metrics
http://localhost:9090

# Service health checks
curl http://localhost:8080/health  # Service B
curl http://localhost:8002/health  # Fast device 
curl http://localhost:8003/health  # Slow device
```

### **Key Metrics to Watch**
- **B error rates**: Should be high 429s during saturation
- **C availability**: Should drop to 0 during high load
- **E2E latency**: Fast (~3s) vs Slow (~10s) devices
- **Request rates**: Throughput patterns by device type

## 🎯 **Testing Strategy**

### **Progressive Testing**
1. **Start with Phase 1** (Cases 1-4): Verify basic functionality
2. **Move to Phase 2** (Cases 5-7): Test under normal load
3. **Phase 3** (Cases 8-10): Test retry storm behavior
4. **Phase 4** (Cases 11-12): Extended stability testing

### **Baseline vs Retry-After Comparison**
- **Baseline**: Current tests (no Retry-After headers)
- **A/B Testing**: Compare Case 10 results with/without Retry-After
- **Key Metrics**: 429 rates, retry amplification, recovery time

## 🛠️ **Troubleshooting**

### **Common Issues**
- **Port conflicts**: Use different ports (8002, 8003) 
- **Docker not running**: Start with `docker compose up -d`
- **Import errors**: Install `pip3 install aiohttp`
- **Connection refused**: Wait for services to start (~10s)

### **Debug Commands**
```bash
# Check container status
docker compose ps

# View service logs
docker compose logs b c d-fast d-slow

# Test direct device access
curl http://localhost:8002/do_work?device_id=test&ms=1000&mode=normal
curl http://localhost:8003/do_work?device_id=test&ms=1000&mode=normal
```