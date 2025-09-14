好的 👍
以下是 **sim-observability-complete.zip** 的完整使用說明，方便你直接上手。

---

# 🚀 使用說明

## 1. 解壓與啟動

```bash
unzip sim-observability-complete.zip -d sim-observability-complete
cd sim-observability-complete
```

啟動整套服務（Tempo + Prometheus + Grafana + B/C/D）：

```bash
docker compose up --build
```

把 **C 擴到 21 個實例**（符合你實際環境的配置）：

```bash
docker compose up -d --scale c=21
```

---

## 2. 驗證服務

* **Grafana** → [http://localhost:3000](http://localhost:3000)

  * Dashboards → **Golden Signals: B & C**
  * Dashboards → **C Availability**
* **Prometheus** → [http://localhost:9090](http://localhost:9090)
* **Tempo (Tracing)** → 透過 Grafana Explore → 選 **Tempo**

健康檢查：

```bash
curl http://localhost:8080/health   # B
curl http://localhost:50051         # C (gRPC，不會直接有 HTTP 回覆)
curl http://localhost:8000/health   # D
```

---

## 3. 發送測試請求

### 正常案例（3 秒完成）

```bash
curl "http://localhost:8080/process?device_id=dev-1&ms=3000&mode=normal"
```

### 慢尾案例（10 秒）

```bash
curl "http://localhost:8080/process?device_id=dev-slow-1&ms=10000&mode=normal"
```

### 掛掉案例（D 不回覆，C 3 秒 timeout）

```bash
curl "http://localhost:8080/process?device_id=dev-hang-1&mode=hang"
```

你會在回覆中看到：

* `504` → timeout
* `429` → busy（`RESOURCE_EXHAUSTED`）
* `503` → connect fail
* `200` → 正常完成

---

## 4. 觀察 Grafana

### Golden Signals: B & C

* **B**

  * Total requests/s
  * Error rate %
  * Latency p50/p95/p99
* **C**

  * Total requests/s
  * Error rate % (`RESOURCE_EXHAUSTED`, `DEADLINE_EXCEEDED`)
  * Processing latency p95/p99

### C Availability

* **Available** vs **Total instances**
* Healthy / Busy / Available 分佈曲線

---

## 5. Trace 分析（Tempo）

在 Grafana → Explore → Tempo：

* 查慢尾請求：

  ```
  { service.name="svc-b", span.duration > 5s }
  ```
* 查掛掉請求（C→D 3s timeout）：

  ```
  { name="/do_work", status!="" }
  ```

你會看到 B → C → D 三段 span，掛掉時 C→D span 約 3 秒後結束，標記 DEADLINE\_EXCEEDED。

---

## 6. PromQL 常用查詢

```promql
# B 每秒請求數
sum(rate(b_requests_total[1m]))

# B 錯誤率 (%)
(sum(rate(b_errors_total[1m])) / sum(rate(b_requests_total[1m]))) * 100

# B 延遲分位數
histogram_quantile(0.95, sum(rate(b_e2e_ms_bucket[5m])) by (le))

# C 可用數
sum((c_healthy==1) and (c_inflight==0))

# C DEADLINE_EXCEEDED (掛掉)
sum(rate(c_errors_total{code="DEADLINE_EXCEEDED"}[5m]))

# C RESOURCE_EXHAUSTED (忙/滿)
sum(rate(c_errors_total{code="RESOURCE_EXHAUSTED"}[5m]))
```

---

## 7. 你會觀察到的「未加強版」特徵

* **429 沒帶 Retry-After** → 上游 A 如果重試，可能造成放大效應
* **B 沒做 connect-fail 單次重試** → 會有一些 UNAVAILABLE 直接反映成 503
* **沒有 Retry Budget** → 高流量下，C 可用數掉更快、B p99 延遲拉更高

---

要不要我幫你做一份 **Markdown 格式的「觀察紀錄表格模板」**，方便你在跑 load test 時記錄下 B/C 的 Requests、Error rate、Latency、Available C 的變化，之後再對比加強版？
