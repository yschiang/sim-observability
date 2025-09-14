# Folders & Topology
- docker-compose brings up Tempo + Prometheus + Grafana + B/C/D
- Grafana provisioned with Tempo & Prometheus datasources and dashboards
- Tracing: OTel → Tempo → Grafana Explore
- Metrics: Prometheus ← B/C/D /metrics → Grafana dashboards