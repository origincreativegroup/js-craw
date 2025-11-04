# Deployment Tools

This directory contains debugging, testing, and deployment tools for the CI/CD pipeline.

## Quick Start

### 1. Run Tests Manually

```bash
python3 scripts/deployment/debug_test_runner.py
```

### 2. Handle a Failure

```bash
python3 scripts/deployment/failure_handler.py \
    "test_failure" \
    "Tests failed" \
    --test-results logs/deployment/test_results_latest.json
```

### 3. Start GitHub Listener

```bash
python3 scripts/deployment/github_listener.py \
    --repo-path /home/admin/js-craw \
    --branch main \
    --interval 60
```

## Files

- `debug_test_runner.py`: Comprehensive test suite runner
- `failure_handler.py`: Handles failures with logging and notifications
- `github_listener.py`: Monitors GitHub and auto-pulls code

## Documentation

See [docs/DEBUGGING_AND_TESTING_PIPELINE.md](../../docs/DEBUGGING_AND_TESTING_PIPELINE.md) for complete documentation.

