---
title: Sustained High CPU Usage on Checkout Service
service: checkout-service
severity: high
tags: [cpu, performance, autoscaling, checkout]
last_updated: 2026-04-08
---

# Sustained High CPU Usage — checkout-service

## Symptoms
- CPU utilization pinned at 95-100% across all replicas despite horizontal pod autoscaler (HPA) scaling to max replica count.
- Request latency degrades gradually rather than failing outright, since the service is CPU-bound, not crashing.
- CPU throttling metrics (`container_cpu_cfs_throttled_seconds_total`) rising sharply.

## Diagnosis
1. Capture a CPU profile under load: `py-spy dump --pid <pid>` (if Python) or the equivalent flame graph for the runtime in use, to identify the hot function.
2. Check for a recently added synchronous, unbounded operation — the most common cause of a step-change in CPU is a new code path doing expensive work (regex on large payloads, unindexed JSON parsing, synchronous cryptographic operations) on the request thread.
3. Cross-reference with the deploy timeline: correlate the exact timestamp CPU usage stepped up with the most recent deployment.

## Root Cause (most recent occurrence)
A new fraud-scoring feature added a synchronous regex-based address-validation check that had catastrophic backtracking behavior on certain malformed address strings, consuming disproportionate CPU per request.

## Resolution
1. Immediate mitigation: feature-flag off the new fraud-scoring check to restore baseline CPU immediately.
2. Root fix: rewrite the offending regex to eliminate catastrophic backtracking (or replace with a non-regex parser), and move the check off the hot request path into an async post-checkout job where latency is not customer-facing.
3. Verify recovery: CPU utilization should return to the 40-60% baseline range under equivalent load.

## Prevention
- Added a regex complexity/backtracking linter to CI for any new pattern touching user input.
- Added CPU-per-request-type dashboards so a single expensive endpoint doesn't hide inside an aggregate service-level metric next time.
