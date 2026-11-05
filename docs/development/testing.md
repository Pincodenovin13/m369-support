# Testing

## Test Pyramid (Phase 1)

| Level | Count | Database |
|---|---|---|
| Unit | 7 | None |
| Integration | 15 | Real PostgreSQL 16 |
| E2E | 0 | (Phase 2+) |

## Running Tests

```bash
cd apps/api

# All tests
pytest tests/ -v

# Unit only (no DB needed)
pytest tests/unit/ -v

# Integration (requires PG)
pytest tests/integration/ -v
```

## Test Status Definitions

- **PASS**: Test was actually executed and succeeded
- **FAIL**: Test was executed and failed
- **BLOCKED**: Could not be executed
- **NOT RUN**: Was not executed

Never report PASS based on code inspection alone.

## Phase 1 Results

22/22 PASSED against real PostgreSQL 16.2.
