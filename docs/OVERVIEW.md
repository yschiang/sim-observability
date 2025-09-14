# Current State Overview
- A(REST) → B(REST) → C(CORBA; simulated as gRPC, single concurrency) → Devices (no proxy)
- C→Devices ~3s typical, up to 10s. If device hangs, only C’s own timeout ends the call.
- Goals: avoid retry storms; visualize E2E & per-hop latency; quantify C availability.