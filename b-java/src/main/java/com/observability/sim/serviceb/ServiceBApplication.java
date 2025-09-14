package com.observability.sim.serviceb;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class ServiceBApplication {

    public static void main(String[] args) {
        // Initialize OpenTelemetry (handled by agent or manual configuration)
        System.out.println("Starting Service B (Spring Boot)...");
        
        SpringApplication.run(ServiceBApplication.class, args);
        
        System.out.println("✓ Service B started successfully");
    }
}