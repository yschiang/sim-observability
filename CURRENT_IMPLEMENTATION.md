# 🔎 ABCD Services Implementation Survey Results

Based on the current codebase analysis and SURVEY.md framework.

---

## 🔎 Service A (Client/Load Generator)
**Status**: Not implemented as core service - Represented by test scripts and load generators

- **Implementation**: `test/simple-load.py`, various test scripts
- **Purpose**: Traffic injection and load testing

### A → B 連線管理分析
基於 `simple-load.py` 實現：

**連線行為**:
- [x] **可以重用既有連線** (HTTP keep-alive through `aiohttp.ClientSession`)
- **連線池**: ClientSession 維護連線池，重用 TCP 連線到 Service B
- **並發模式**: `asyncio.create_task()` 實現異步並發請求
- **連線超時**: 10 秒總超時 (`ClientTimeout(total=10)`)

---

## 🔎 Service B (FastAPI Gateway) 
**File**: `/b/app.py`

### 1. 執行模型
- [x] 其他：**單進程 + 異步並發** (FastAPI + uvicorn + asyncio event loop)

### 2. 連線管理  
- [x] 可以重用既有連線 (gRPC channel reuse to C, HTTP keep-alive)

### 3. 請求併發能力
- [x] 沒有明確限制，取決於 OS / 資源 (async event loop)

### 4. 排隊行為
- [x] 不確定 → 描述：依賴 FastAPI/uvicorn 內建隊列，無明確限制

### 5. Timeout 設定
- Connect timeout = **1000ms** (`CONNECT_TIMEOUT_S=1.0`)
- Request / Process timeout = **10000ms** (`REQUEST_TIMEOUT_S=10.0`)

### 6. Retry 行為
- 會重試的情況：**gRPC connection 層面自動重試** (when `ENABLE_B_TO_C_RETRIES=true`)
- 最大重試次數：**2** (`MAX_B_TO_C_RETRIES=2`) 
- 是否會換不同 instance？ [x] **Yes** (round_robin load balancing)
- 不會重試的情況：**應用層錯誤 (4xx, 5xx)**

**Endpoints**:
- `GET /health` - Health check
- `GET /__status` - Service status with available C instances estimate
- `GET /process` - Main processing endpoint

**Metrics**: `b_total_received`, `b_completed`, `b_failed`, `b_errors_total`, `b_e2e_ms`

---

## 🔎 Service C (gRPC Processor) - **系統瓶頸**
**File**: `/c/server.py`

### 1. 執行模型
- [x] 單線程 / 單進程 (asyncio event loop)

### 2. 連線管理
- [x] 可以重用既有連線 (gRPC server accepts persistent connections)

### 3. 請求併發能力  
- [x] 僅能處理 **1 個** (`Semaphore(1)` - **🚨 核心約束**)

### 4. 排隊行為
- [x] 直接被拒絕 (超過 semaphore 容量立即回 `RESOURCE_EXHAUSTED`)

### 5. Timeout 設定
- Connect timeout = **N/A** (server side)
- Request / Process timeout = **60000ms** (`DEVICE_TIMEOUT_S=60.0` to downstream D)

### 6. Retry 行為
- 會重試的情況：**無應用層重試** (`ENABLE_C_TO_D_RETRIES=false`)
- 最大重試次數：**0** (`MAX_C_TO_D_RETRIES=0`)
- 是否會換不同 instance？ [ ] **No**
- 不會重試的情況：**所有 D 服務錯誤都直接返回**

**Service Definition**: 
- gRPC `DeviceProxyServicer` 
- Method: `Process(ProcessRequest) -> ProcessReply`

**Device Routing Logic**:
- `device_id` contains "slow" → routes to `D_SLOW_URL` 
- Otherwise → routes to `D_FAST_URL`

**Metrics**: `c_healthy`, `c_inflight`, `c_ejected`, `c_total_received`, `c_completed`, `c_failed`, `c_errors_total`, `c_process_ms`, `c_to_d_ms`

**Current Scaling**: **10 instances** (docker-compose scale)

---

## 🔎 Service D (Device Simulator)
**Files**: `/d/app.py` (single instance in current setup)

### 1. 執行模型
- [x] 單線程 / 單進程 (FastAPI with uvicorn async event loop)

### 2. 連線管理
- [x] 可以重用既有連線 (HTTP keep-alive)

### 3. 請求併發能力
- [x] 沒有明確限制，取決於 OS / 資源 (async event loop)

### 4. 排隊行為
- [x] 不確定 → 描述：依賴 FastAPI/uvicorn 內建隊列，無明確限制

### 5. Timeout 設定
- Connect timeout = **N/A** (server side)
- Request / Process timeout = **由 mode 參數控制**
  - `mode=normal`: ~3000ms simulation
  - `mode=slow`: 15000ms+ simulation

### 6. Retry 行為
- 會重試的情況：**N/A** (terminal service)
- 最大重試次數：**N/A**
- 是否會換不同 instance？ **N/A**
- 不會重試的情況：**N/A**

**Endpoints**:
- `GET /health` - Health check  
- `GET /do_work` - Device work simulation

**Device Types** (configured but single instance):
- `d-fast`: Low latency simulation
- `d-slow`: High latency simulation  

---

## 🎯 系統架構總結

### Request Flow
```
A (Load Generator) → B (FastAPI Gateway) → C (gRPC Processor) → D (Device Simulator)
```

### 關鍵約束與設計
1. **系統瓶頸**: Service C 的 `Semaphore(1)` 限制每個實例同時只能處理 1 個請求
2. **擴展策略**: Service C 可水平擴展 (當前: 10 instances)
3. **負載均衡**: B → C 使用 gRPC `round_robin` 
4. **設備路由**: C → D 根據 `device_id` 模式路由
5. **錯誤處理**: 鏈式錯誤傳播，無中間重試

### Configuration Management
- **Environment Files**: `config/baseline.env`, `config/tunable.env`
- **Docker Compose**: Service scaling and networking
- **Prometheus**: Service discovery for C instances (`dns_sd_configs`)

### 監控覆蓋
- ✅ **Prometheus Metrics**: All services instrumented
- ✅ **Grafana Dashboards**: 
  - Golden Signals (Requests/s, Error Rate, Latency)
  - Service C Instance Table with state indicators
- ✅ **OpenTelemetry Tracing**: End-to-end distributed tracing
- ✅ **Service States**: 
  - 🟢 Available (healthy=1, inflight=0)
  - 🟡 Processing (healthy=1, inflight=1) 
  - 🔴 Down (healthy=0)

### Current Deployment Status
- **Service B**: 1 instance, port 8080 (HTTP) + 8081 (metrics)
- **Service C**: 10 instances, port 50051 (gRPC) + dynamic metrics ports
- **Service D**: 1 instance, port 8000 (HTTP) + 9100 (metrics)
- **Prometheus**: Port 9090
- **Grafana**: Port 3000

---

## 🚨 已識別問題點

1. **Single-threaded Bottleneck**: Service C's `Semaphore(1)` creates artificial contention
2. **No Request Queuing**: C instances immediately reject excess load 
3. **No Circuit Breaker**: No upstream protection against downstream failures
4. **Limited Device Simulation**: Only single D instance despite fast/slow routing
5. **Retry Storm Potential**: B→C retry configuration could amplify load

---

*Last Updated: Based on commit `3f94a04` - Service C instance monitoring dashboard implementation*