# Service B - Java Spring Boot Implementation

This is a Java Spring Boot reimplementation of Service B, maintaining API compatibility with the original Python FastAPI version.

## 🎯 Purpose

Demonstrates how to migrate Service B from Python/FastAPI to Java/Spring Boot while:
- Maintaining identical REST API endpoints 
- Preserving gRPC client behavior and retry logic
- Keeping the same Prometheus metrics structure
- Supporting the same configuration parameters

## 🏗️ Architecture

- **Framework**: Spring Boot 3.2.0 + Java 17
- **gRPC Client**: grpc-java with round-robin load balancing  
- **Metrics**: Micrometer + Prometheus
- **Tracing**: OpenTelemetry Java Agent
- **Configuration**: YAML-based with environment variable overrides

## 📋 API Compatibility

### REST Endpoints
- `GET /health` - Health check (`{"ok": true}`)
- `GET /__status` - Service status with C instance estimate
- `GET /process?device_id=dev-1&ms=3000&mode=normal` - Main processing

### Metrics (Prometheus)
- `b_total_received` - Counter with endpoint tag
- `b_completed` - Counter with endpoint tag  
- `b_failed` - Counter with endpoint tag
- `b_errors_total` - Counter with code+endpoint tags
- `b_e2e_ms` - Timer histogram with endpoint tag
- `b_available_c_instances` - Gauge

## 🔧 Configuration

### Environment Variables (same as Python version)
- `APP_C_TARGET` - gRPC target (default: c:50051)
- `APP_CONNECT_TIMEOUT_MS` - Connection timeout (default: 1000)
- `APP_REQUEST_TIMEOUT_MS` - Request timeout (default: 10000)
- `APP_MAX_B_TO_C_RETRIES` - Max retries (default: 2)
- `APP_ENABLE_B_TO_C_RETRIES` - Enable retries (default: true)
- Error mapping flags (same as Python version)

### Spring Boot Configuration
See `src/main/resources/application.yml` for full configuration.

## 🚀 Running

### Using Docker Compose (Java Profile)
```bash
# Run with Java Spring Boot Service B
docker-compose --profile java up

# Run with original Python Service B  
docker-compose --profile python up

# Default (no profile) - runs Python version for compatibility
docker-compose up
```

### Local Development
```bash
cd b-java
mvn spring-boot:run
```

## 🔄 Behavioral Differences

### Concurrency Model
- **Python (asyncio)**: Single-threaded event loop
- **Java (Spring Boot)**: Multi-threaded Tomcat container with thread pool
- **Impact**: Better CPU utilization on multi-core systems

### Memory Usage
- **Python**: Lower memory footprint, but GIL limits CPU parallelism
- **Java**: Higher memory usage (JVM overhead), but true multi-threading

### gRPC Client
- **Python**: Uses asyncio gRPC client
- **Java**: Uses blocking gRPC client with thread pool
- **Both**: Same round-robin load balancing and retry behavior

## 📊 Performance Characteristics

Expected differences when running Java vs Python version:
1. **Throughput**: Java may handle more concurrent requests
2. **Latency**: Similar p50/p95, Java may have better p99 under load
3. **Resource Usage**: Java uses more memory, potentially better CPU utilization
4. **Cold Start**: Java has longer startup time due to JVM initialization

## ⚡ Quick Test

```bash
# Test health endpoint
curl http://localhost:8080/health

# Test process endpoint  
curl "http://localhost:8080/process?device_id=dev-fast-1&ms=1000&mode=normal"

# Check metrics
curl http://localhost:8081/actuator/prometheus | grep ^b_
```

## 🐛 Known Limitations

1. **Available C Instances**: Currently returns placeholder value, needs implementation
2. **Retry Logic**: Basic implementation, may need fine-tuning for exact Python behavior
3. **Error Handling**: HTTP status codes should match Python version exactly

This implementation serves as a proof-of-concept for migrating microservices between technology stacks while maintaining operational compatibility.