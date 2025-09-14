package com.observability.sim.serviceb.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "app")
public class AppConfiguration {
    
    private String cTarget = "c:50051";
    private int connectTimeoutMs = 1000;
    private int requestTimeoutMs = 10000;
    private int maxBToCRetries = 2;
    private boolean enableBToCRetries = true;
    private int bToCRetryBackoffMs = 100;
    private boolean mapResourceExhaustedTo429 = false;
    private boolean mapUnavailableTo503 = false;
    private boolean mapDeadlineExceededTo504 = false;
    
    // Getters and Setters
    public String getCTarget() {
        return cTarget;
    }
    
    public void setCTarget(String cTarget) {
        this.cTarget = cTarget;
    }
    
    public int getConnectTimeoutMs() {
        return connectTimeoutMs;
    }
    
    public void setConnectTimeoutMs(int connectTimeoutMs) {
        this.connectTimeoutMs = connectTimeoutMs;
    }
    
    public int getRequestTimeoutMs() {
        return requestTimeoutMs;
    }
    
    public void setRequestTimeoutMs(int requestTimeoutMs) {
        this.requestTimeoutMs = requestTimeoutMs;
    }
    
    public int getMaxBToCRetries() {
        return maxBToCRetries;
    }
    
    public void setMaxBToCRetries(int maxBToCRetries) {
        this.maxBToCRetries = maxBToCRetries;
    }
    
    public boolean isEnableBToCRetries() {
        return enableBToCRetries;
    }
    
    public void setEnableBToCRetries(boolean enableBToCRetries) {
        this.enableBToCRetries = enableBToCRetries;
    }
    
    public int getBToCRetryBackoffMs() {
        return bToCRetryBackoffMs;
    }
    
    public void setBToCRetryBackoffMs(int bToCRetryBackoffMs) {
        this.bToCRetryBackoffMs = bToCRetryBackoffMs;
    }
    
    public boolean isMapResourceExhaustedTo429() {
        return mapResourceExhaustedTo429;
    }
    
    public void setMapResourceExhaustedTo429(boolean mapResourceExhaustedTo429) {
        this.mapResourceExhaustedTo429 = mapResourceExhaustedTo429;
    }
    
    public boolean isMapUnavailableTo503() {
        return mapUnavailableTo503;
    }
    
    public void setMapUnavailableTo503(boolean mapUnavailableTo503) {
        this.mapUnavailableTo503 = mapUnavailableTo503;
    }
    
    public boolean isMapDeadlineExceededTo504() {
        return mapDeadlineExceededTo504;
    }
    
    public void setMapDeadlineExceededTo504(boolean mapDeadlineExceededTo504) {
        this.mapDeadlineExceededTo504 = mapDeadlineExceededTo504;
    }
}