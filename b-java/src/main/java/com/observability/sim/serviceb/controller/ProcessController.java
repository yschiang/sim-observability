package com.observability.sim.serviceb.controller;

import com.observability.sim.serviceb.config.AppConfiguration;
import com.observability.sim.serviceb.service.GrpcClientService;
import com.observability.sim.deviceproxy.DeviceProxyProto.ProcessReply;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@RestController
public class ProcessController {
    
    private final GrpcClientService grpcClientService;
    private final AppConfiguration appConfig;
    
    @Autowired
    public ProcessController(GrpcClientService grpcClientService, AppConfiguration appConfig) {
        this.grpcClientService = grpcClientService;
        this.appConfig = appConfig;
    }
    
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        Map<String, Object> response = new HashMap<>();
        response.put("ok", true);
        return ResponseEntity.ok(response);
    }
    
    @GetMapping("/__status")
    public ResponseEntity<Map<String, Object>> status() {
        Map<String, Object> response = new HashMap<>();
        // This would need to be implemented to get actual available C instances
        response.put("available_estimate", 1.0);
        return ResponseEntity.ok(response);
    }
    
    @GetMapping("/process")
    public ResponseEntity<Object> process(
            @RequestParam(name = "device_id", defaultValue = "dev-1") String deviceId,
            @RequestParam(defaultValue = "3000") int ms,
            @RequestParam(defaultValue = "normal") String mode) {
        
        String requestId = UUID.randomUUID().toString();
        Instant startTime = Instant.now();
        
        try {
            ProcessReply reply = grpcClientService.processRequest(deviceId, ms, mode);
            
            Duration e2eDuration = Duration.between(startTime, Instant.now());
            double e2eMs = e2eDuration.toMillis();
            
            // Prepare response
            Map<String, Object> responseBody = new HashMap<>();
            responseBody.put("device_id", reply.getDeviceId());
            responseBody.put("cost_ms", reply.getCostMs());
            
            // Add custom headers
            Map<String, String> headers = new HashMap<>();
            headers.put("X-Request-Id", requestId);
            headers.put("Server-Timing", String.format("e2e;dur=%.1f", e2eMs));
            
            return ResponseEntity.ok()
                    .header("X-Request-Id", requestId)
                    .header("Server-Timing", String.format("e2e;dur=%.1f", e2eMs))
                    .body(responseBody);
                    
        } catch (StatusRuntimeException e) {
            Duration e2eDuration = Duration.between(startTime, Instant.now());
            double e2eMs = e2eDuration.toMillis();
            
            Status.Code code = e.getStatus().getCode();
            
            // Error mapping based on configuration
            HttpStatus httpStatus = mapGrpcStatusToHttp(code);
            String errorMessage = mapGrpcStatusToMessage(code, e2eMs);
            
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("error", errorMessage);
            errorResponse.put("grpc_code", code.name());
            errorResponse.put("latency_ms", e2eMs);
            
            return ResponseEntity.status(httpStatus)
                    .header("X-Request-Id", requestId)
                    .header("Server-Timing", String.format("e2e;dur=%.1f", e2eMs))
                    .body(errorResponse);
                    
        } catch (Exception e) {
            Duration e2eDuration = Duration.between(startTime, Instant.now());
            double e2eMs = e2eDuration.toMillis();
            
            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("error", String.format("upstream timeout %.1fms", e2eMs));
            errorResponse.put("type", "timeout");
            errorResponse.put("latency_ms", e2eMs);
            
            return ResponseEntity.status(HttpStatus.GATEWAY_TIMEOUT)
                    .header("X-Request-Id", requestId)
                    .header("Server-Timing", String.format("e2e;dur=%.1f", e2eMs))
                    .body(errorResponse);
        }
    }
    
    private HttpStatus mapGrpcStatusToHttp(Status.Code code) {
        switch (code) {
            case RESOURCE_EXHAUSTED:
                return appConfig.isMapResourceExhaustedTo429() ? 
                    HttpStatus.TOO_MANY_REQUESTS : HttpStatus.BAD_GATEWAY;
                    
            case UNAVAILABLE:
                return appConfig.isMapUnavailableTo503() ? 
                    HttpStatus.SERVICE_UNAVAILABLE : HttpStatus.BAD_GATEWAY;
                    
            case DEADLINE_EXCEEDED:
                return appConfig.isMapDeadlineExceededTo504() ? 
                    HttpStatus.GATEWAY_TIMEOUT : HttpStatus.BAD_GATEWAY;
                    
            default:
                return HttpStatus.BAD_GATEWAY;
        }
    }
    
    private String mapGrpcStatusToMessage(Status.Code code, double e2eMs) {
        switch (code) {
            case RESOURCE_EXHAUSTED:
                return "C/D busy";
                
            case UNAVAILABLE:
                return "C connect fail";
                
            case DEADLINE_EXCEEDED:
                return "upstream timeout";
                
            default:
                return String.format("grpc error: %s", code.name());
        }
    }
}