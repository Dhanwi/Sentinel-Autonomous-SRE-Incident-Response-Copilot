---
title: Redis Sentinel Failover Causing Cache Stampede
service: cache-service
severity: high
tags: [redis, sentinel, failover, cache-stampede]
last_updated: 2026-03-27
---

# Redis Sentinel Failover — Cache Stampede

## Symptoms
- Brief but severe latency spike (10-30 seconds) across all services depending on the shared cache layer.
- Database CPU spikes sharply during the same window — the classic signature of a cache stampede, where cache misses suddenly force all traffic through to the database at once.
- Redis Sentinel logs show a `+switch-master` event immediately preceding the spike.

## Diagnosis
1. Confirm the failover event: `redis-cli -p 26379 SENTINEL master mymaster` and check Sentinel logs for `+switch-master` timestamps.
2. Confirm cache-miss correlation: cache hit-rate dashboards should show a sharp drop to near-zero at the exact failover timestamp, since clients briefly connect to a cold replica-turned-master with no warmed data.
3. Confirm this is failover-induced and not a genuine node failure by checking that the new master is healthy and simply lacks the previous master's in-memory dataset (replication lag prior to failover, or a cold start).

## Root Cause (most recent occurrence)
Sentinel triggered a failover due to a transient network partition (not an actual Redis crash); the promoted replica had several seconds of replication lag, so a meaningful slice of recently-cached keys were missing, causing simultaneous cache misses across all clients for those keys.

## Resolution
1. Immediate mitigation: the stampede self-resolves once the new master repopulates from normal traffic, typically within 30-60 seconds — no manual action usually required beyond monitoring.
2. Root fix: implement request coalescing/locking on cache-miss (only one request per key fetches from DB and repopulates cache; concurrent requests for the same key wait on that result) to prevent the thundering-herd effect on any future failover.
3. Verify recovery: database CPU and cache hit-rate should both return to baseline within 1-2 minutes of the failover event.

## Prevention
- Implemented cache-miss request coalescing (see Root fix) as a standing mitigation, not just for this incident.
- Tuned Sentinel's `down-after-milliseconds` slightly upward to reduce false-positive failovers triggered by brief network blips.
