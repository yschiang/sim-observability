# Claude Rules
- Don’t alter timeout/retry semantics without updating docs.
- Keep C single concurrency; B fails fast on busy.
- Tracing must be enabled; metrics must expose Golden Signals.
- /health must not hit downstream.