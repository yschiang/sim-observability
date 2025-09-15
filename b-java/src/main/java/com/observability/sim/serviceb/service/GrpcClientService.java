package com.observability.sim.serviceb.service;

import com.observability.sim.serviceb.config.AppConfiguration;
import com.observability.sim.deviceproxy.DeviceProxyGrpc;
import com.observability.sim.deviceproxy.DeviceProxyProto.ProcessRequest;
import com.observability.sim.deviceproxy.DeviceProxyProto.ProcessReply;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.StatusRuntimeException;
import io.grpc.stub.StreamObserver;
import io.grpc.Metadata;
import io.grpc.ClientInterceptor;
import io.grpc.ClientCall;
import io.grpc.MethodDescriptor;
import io.grpc.CallOptions;
import io.grpc.ForwardingClientCall;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.context.Context;
import io.opentelemetry.context.propagation.TextMapSetter;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Service
public class GrpcClientService {
    
    // Custom interceptor to inject trace context into gRPC metadata
    private static class TraceContextInterceptor implements ClientInterceptor {
        private final TextMapSetter<Metadata> setter = new TextMapSetter<Metadata>() {
            @Override
            public void set(Metadata carrier, String key, String value) {
                carrier.put(Metadata.Key.of(key, Metadata.ASCII_STRING_MARSHALLER), value);
            }
        };

        @Override
        public <ReqT, RespT> ClientCall<ReqT, RespT> interceptCall(
                MethodDescriptor<ReqT, RespT> method,
                CallOptions callOptions,
                io.grpc.Channel next) {
            
            return new ForwardingClientCall.SimpleForwardingClientCall<ReqT, RespT>(next.newCall(method, callOptions)) {
                @Override
                public void start(Listener<RespT> responseListener, Metadata headers) {
                    // Inject current trace context into gRPC metadata
                    GlobalOpenTelemetry.getPropagators()
                            .getTextMapPropagator()
                            .inject(Context.current(), headers, setter);
                    
                    // Debug: Print headers being sent
                    System.out.println("DEBUG: Sending gRPC headers:");
                    for (String key : headers.keys()) {
                        if (key.toLowerCase().contains("trace")) {
                            System.out.println("  " + key + ": " + headers.get(Metadata.Key.of(key, Metadata.ASCII_STRING_MARSHALLER)));
                        }
                    }
                    
                    super.start(responseListener, headers);
                }
            };
        }
    }
    
    private final AppConfiguration appConfig;
    private final MeterRegistry meterRegistry;
    
    private ManagedChannel channel;
    private DeviceProxyGrpc.DeviceProxyBlockingStub blockingStub;
    
    // Metrics
    private Counter totalReceivedCounter;
    private Counter completedCounter;
    private Counter failedCounter;
    private Counter errorsCounter;
    private Timer latencyTimer;
    private Timer failedLatencyTimer;
    private Gauge availableGauge;
    
    @Autowired
    public GrpcClientService(AppConfiguration appConfig, MeterRegistry meterRegistry) {
        this.appConfig = appConfig;
        this.meterRegistry = meterRegistry;
    }
    
    @PostConstruct
    public void init() {
        // gRPC channel with trace context propagation
        this.channel = ManagedChannelBuilder.forTarget(appConfig.getCTarget())
                .usePlaintext()
                .intercept(new TraceContextInterceptor())
                .build();
                
        this.blockingStub = DeviceProxyGrpc.newBlockingStub(channel);
        
        // Initialize metrics
        initializeMetrics();
        
        System.out.println("✓ gRPC client initialized for target: " + appConfig.getCTarget());
    }
    
    private void initializeMetrics() {
        this.totalReceivedCounter = Counter.builder("b_total_received")
                .description("Total requests received")
                .tag("endpoint", "/process")
                .register(meterRegistry);
                
        this.completedCounter = Counter.builder("b_completed")
                .description("Successfully completed requests") 
                .tag("endpoint", "/process")
                .register(meterRegistry);
                
        this.failedCounter = Counter.builder("b_failed")
                .description("Failed requests")
                .tag("endpoint", "/process")
                .register(meterRegistry);
                
        this.errorsCounter = Counter.builder("b_errors_total")
                .description("Total error responses")
                .tag("code", "unknown")
                .tag("endpoint", "/process")
                .register(meterRegistry);
                
        this.latencyTimer = Timer.builder("b_e2e_ms")
                .description("End-to-end latency (ms)")
                .tag("endpoint", "/process")
                .register(meterRegistry);
                
        this.failedLatencyTimer = Timer.builder("b_failed_e2e_ms")
                .description("End-to-end latency for failed requests (ms)")
                .tag("endpoint", "/process")
                .register(meterRegistry);
                
        // Register gauge differently 
        meterRegistry.gauge("b_available_c_instances", this, obj -> obj.getAvailableInstances());
    }
    
    public ProcessReply processRequest(String deviceId, int ms, String mode) throws Exception {
        totalReceivedCounter.increment();
        
        Timer.Sample sample = Timer.start(meterRegistry);
        
        try {
            // Wait for channel to be ready (like Python does)
            if (!channel.getState(true).equals(io.grpc.ConnectivityState.READY)) {
                System.out.println("Waiting for gRPC channel to be ready...");
                // Give it some time to connect
                Thread.sleep(100);
            }
            
            ProcessRequest request = ProcessRequest.newBuilder()
                    .setDeviceId(deviceId)
                    .setMs(ms)
                    .setMode(mode)
                    .build();
            
            // Simple blocking call with timeout
            ProcessReply reply = blockingStub
                    .withDeadlineAfter(appConfig.getRequestTimeoutMs(), TimeUnit.MILLISECONDS)
                    .process(request);
            
            sample.stop(latencyTimer);
            completedCounter.increment();
            
            return reply;
            
        } catch (StatusRuntimeException e) {
            sample.stop(failedLatencyTimer);
            failedCounter.increment();
            
            // Record error by gRPC status code
            Counter.builder("b_errors_total")
                    .tag("code", e.getStatus().getCode().name())
                    .tag("endpoint", "/process")
                    .register(meterRegistry)
                    .increment();
                    
            throw e;
        }
    }
    
    private double getAvailableInstances() {
        // This would need to be implemented to query C service instances
        // For now, return a placeholder value
        return 1.0;
    }
    
    @PreDestroy
    public void shutdown() {
        if (channel != null) {
            channel.shutdown();
            try {
                if (!channel.awaitTermination(5, TimeUnit.SECONDS)) {
                    channel.shutdownNow();
                }
            } catch (InterruptedException e) {
                channel.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }
    }
}