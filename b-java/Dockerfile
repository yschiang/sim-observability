# Multi-stage build for Spring Boot Service B
FROM maven:3.9.5-eclipse-temurin-17 AS build

WORKDIR /app

# Copy pom.xml first for dependency caching
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy source code and proto files
COPY src src/

# Build the application
RUN mvn clean package -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-jammy

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy built JAR
COPY --from=build /app/target/service-b-*.jar app.jar

# Download OpenTelemetry Java Agent
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar otel-agent.jar

# Set ownership
RUN chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080 8081

# Run with OpenTelemetry agent
CMD ["java", \
     "-javaagent:otel-agent.jar", \
     "-Dotel.service.name=svc-b", \
     "-Dotel.exporter.otlp.traces.endpoint=http://tempo:4318/v1/traces", \
     "-Dotel.exporter.otlp.protocol=http/protobuf", \
     "-Dotel.metrics.exporter=none", \
     "-Dotel.logs.exporter=none", \
     "-Dotel.instrumentation.grpc.enabled=true", \
     "-Dotel.propagators=tracecontext,baggage", \
     "-Dotel.javaagent.debug=true", \
     "-jar", "app.jar"]