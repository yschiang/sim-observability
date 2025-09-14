# Retry Matrix (A → B → C → D)

| Hop                                       | When to Retry                                                                               | Max Retries                   | Backoff (suggested)                                                                    | Don’t Retry If                                                                   | Return / Map                                                                                   |
| ----------------------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **A → B (REST)**                          | On **429/503** with `Retry-After`, or transient network errors (connect reset/DNS/TLS)      | 2–3                           | Exponential + full jitter (base 200–400 ms, cap 2–4 s; honor `Retry-After` if present) | **504** after full B timeout, **4xx** other than 429, writes without idempotency | Surface last status to caller                                                                  |
| **B → C**<br>(CORBA in prod; gRPC in sim) | Only on **connect-failure before request is sent** (e.g., connection refused / unavailable) | 1 (to a different C instance) | Fixed 50–150 ms or jittered 100 ms                                                     | `RESOURCE_EXHAUSTED`, `DEADLINE_EXCEEDED`, `INTERNAL` after headers sent         | Map to HTTP: 429 (busy), 504 (timeout), 503 (connect fail)                                     |
| **C → D (Devices)**                       | **Never** (devices are bottleneck; retries amplify load)                                    | 0                             | —                                                                                      | Any 4xx/5xx, timeouts                                                            | Map to gRPC: 429 → `RESOURCE_EXHAUSTED`; timeout → `DEADLINE_EXCEEDED`; others → `UNAVAILABLE` |

---

## Rationale (quick checks)

* Retry **only** on transport/connect failures upstream.
* Once a request may have executed downstream, **do not retry** (avoid double execution).
* Busy signals propagate upward: D busy → C `RESOURCE_EXHAUSTED` → B 429 + `Retry-After` → A backs off.
* Timeouts are **terminal at that hop**: C’s \~3 s device timeout → B should not retry; A may retry with backoff.

---

## Concrete Settings (match simulation)

* **B → C**

  * `connect_timeout`: **0.35 s**
  * `request_timeout`: **≤ 3 s**
  * `max_connect_retries`: **1** (to a different C)
  * gRPC codes:

    * `UNAVAILABLE` (pre-send) → retry once
    * `RESOURCE_EXHAUSTED` → no retry → 429
    * `DEADLINE_EXCEEDED` → no retry → 504

* **C → D**

  * `request_timeout`: \~**3.0 s** (e.g., 2.8–3.0)
  * **No retries**
  * On 429 → `RESOURCE_EXHAUSTED`; on timeout → `DEADLINE_EXCEEDED`

* **A → B**

  * Max total attempts **3–4** (1 original + 2–3 retries)
  * Backoff: `sleep = random(0, base * 2^attempt)` with cap 2–4 s
  * Honor `Retry-After`; if both backoff and `Retry-After` exist, wait **max** of the two

---

## Guardrails & Monitoring

* **Retry budget**: keep B’s (and A’s) retries ≤ 30% of originals; if exceeded → 429 early.
* **Headers**: B should return `Retry-After: 0.1–0.3 s` on 429.
* **Dashboards**: monitor error rate, p95/p99 latency, and **Available C**.

  * Spikes after partial outage = retry amplification → tighten backoff/budgets.