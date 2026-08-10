---
title: Redis Connection Pool Exhaustion
service: checkout-service
severity: high
tags: [redis, connection-pool, timeout, checkout]
last_updated: 2026-03-14
---

# Redis Connection Pool Exhaustion — checkout-service

## Symptoms
- `checkout-service` returns HTTP 503 on the `/cart/checkout` endpoint.
- Application logs show repeated `ERROR: connection pool exhausted (redis-pool-1)`.
- p99 latency on checkout requests climbs above 8s before requests start failing outright.
- Redis server itself shows normal CPU/memory — the bottleneck is client-side pool sizing, not the Redis instance.

## Diagnosis
1. Check current pool utilization: `redis-cli -h $REDIS_HOST CLIENT LIST | wc -l` compared against the configured `max_connections` in `checkout-service`'s Redis client config.
2. Confirm no long-running or leaked connections: look for clients with high `age` and idle `idle` time in `CLIENT LIST` output.
3. Correlate with a recent deploy — pool exhaustion is most often caused by a new code path that opens a connection per-request instead of reusing the pooled client (a common regression when someone bypasses the shared client singleton).

## Root Cause (most recent occurrence)
A refactor introduced a new `PaymentValidator` class that instantiated its own Redis client instead of reusing the app-wide pooled client, silently doubling effective connection demand under load.

## Resolution
1. Immediate mitigation: increase `max_connections` on the pool via the `REDIS_POOL_MAX_CONNECTIONS` env var and restart the affected pods to relieve pressure.
2. Root fix: audit all Redis client instantiations in the codebase; ensure every consumer uses the shared `get_redis_client()` singleton.
3. Verify recovery: p99 latency should return to baseline (<200ms) within 2 minutes of the restart.

## Prevention
- Added a lint rule flagging direct `redis.Redis(...)` instantiation outside `app/core/redis_client.py`.
- Added a Grafana alert on pool utilization exceeding 80% for 3+ minutes, well before exhaustion.