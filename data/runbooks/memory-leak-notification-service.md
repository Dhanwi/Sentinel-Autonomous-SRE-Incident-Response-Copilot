---
title: Gradual Memory Leak in Notification Service
service: notification-service
severity: medium
tags: [memory-leak, nodejs, oom, notifications]
last_updated: 2026-02-02
---

# Gradual Memory Leak — notification-service

## Symptoms
- Pod memory usage climbs steadily over 6-8 hours from a baseline of ~250MB to the 1GB container limit.
- `OOMKilled` events appear in `kubectl describe pod` roughly once per day per replica.
- No corresponding increase in request volume — the leak is time-correlated, not traffic-correlated.

## Diagnosis
1. Capture a heap snapshot before and after a few hours of runtime: `node --inspect` + Chrome DevTools memory profiler, or `clinic heapprofiler` in CI.
2. Compare snapshots for retained object growth — in this service, look specifically at the `EventEmitter` listener count via `process.listenerCount('notification:sent')`.
3. Confirm via `node --trace-warnings` for `MaxListenersExceededWarning`, which is the canonical symptom of listener-based leaks.

## Root Cause (most recent occurrence)
Each incoming webhook handler registered a new listener on a shared `EventEmitter` without ever removing it on request completion, so listeners accumulated indefinitely as long-lived process uptime increased.

## Resolution
1. Immediate mitigation: reduce pod memory limit checks and increase replica count to spread load, and schedule a rolling restart every 4 hours as a stopgap.
2. Root fix: add `emitter.removeListener(...)` in a `finally` block for every handler that subscribes per-request; alternatively refactor to a single long-lived listener with an internal routing table instead of one listener per request.
3. Verify recovery: heap should plateau (not grow linearly) over a 12-hour soak test before considering this closed.

## Prevention
- Added a memory-growth alert: pod RSS growing >5% per hour sustained for 2+ hours triggers a warning, well before OOMKill territory.
- Added `--max-old-space-size` explicit flag plus heap-snapshot-on-SIGUSR2 for faster future diagnosis.