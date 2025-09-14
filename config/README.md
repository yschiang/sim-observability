# Configuration System

## Purpose
- **baseline.env**: Preserve current implementation for comparison
- **tunable.env**: Experimental configuration for retry/timeout tuning

## Usage

### Run Baseline (Current Implementation)
```bash
# Use current defaults (baseline behavior)
docker compose up -d

# Or explicitly use baseline config
docker compose --env-file config/baseline.env up -d
python3 test/simple-load.py --testcase 10
```

### Run Experiments (Tunable Parameters)
```bash
# Experiment with different timeout/retry settings
docker compose --env-file config/tunable.env up -d
python3 test/simple-load.py --testcase 10

# Quick parameter changes (override specific values)
CONNECT_TIMEOUT_S=1.0 ENABLE_B_TO_C_RETRIES=true docker compose up -d
```

### Compare Results
```bash
# 1. Run baseline
docker compose --env-file config/baseline.env up -d
python3 test/simple-load.py --testcase 10 > results-baseline.txt

# 2. Run experiment  
docker compose down
docker compose --env-file config/tunable.env up -d
python3 test/simple-load.py --testcase 10 > results-experiment.txt

# 3. Compare
diff results-baseline.txt results-experiment.txt
```

## Key Parameters to Experiment With

### Connection & Request Timeouts
- `CONNECT_TIMEOUT_S`: 0.1, 0.35, 1.0 (how long to wait for C connection)
- `REQUEST_TIMEOUT_S`: 1.0, 3.0, 10.0 (how long B waits for C response)
- `DEVICE_TIMEOUT_S`: 1.0, 3.0, 8.0 (how long C waits for device)

### Retry Behavior  
- `ENABLE_B_TO_C_RETRIES`: false → true (enable B→C retries)
- `MAX_B_TO_C_RETRIES`: 0, 1, 3 (how many times B retries C)
- `ENABLE_RETRY_AFTER_HEADERS`: false → true (add backoff guidance)

### Expected Observations
- **Shorter timeouts**: More 504 errors, faster failure detection
- **Longer timeouts**: Higher latency, fewer false timeouts  
- **Enable retries**: Higher success rates, potential retry storms
- **Retry-After headers**: Better client backoff behavior