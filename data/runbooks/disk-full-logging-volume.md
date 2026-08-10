---
title: Disk Full on Logging Volume
service: logging-service
severity: critical
tags: [disk, logging, storage, outage]
last_updated: 2026-02-21
---

# Disk Full — Logging Volume

## Symptoms
- Application pods across multiple services begin failing to write logs; some services (those with synchronous log writes) start throwing write errors and become unresponsive entirely.
- `df -h` on the logging volume shows 100% utilization.
- Log ingestion pipeline (Fluentd/Vector) reports `no space left on device` errors.

## Diagnosis
1. Confirm the immediate cause: `du -sh /var/log/* | sort -rh | head -10` to identify which service/log file is consuming disproportionate space.
2. Check for a recent change in log verbosity — the most common cause is a `DEBUG`-level log statement accidentally left enabled in a production deploy, generating orders of magnitude more log volume than normal.
3. Check log rotation configuration (`logrotate` or equivalent) is actually running and not silently failing — a full disk is often a rotation failure compounding with a volume spike, not either alone.

## Root Cause (most recent occurrence)
A debug flag intended for a staging-only deploy was accidentally included in a production config change, causing one service to log full request/response payloads at DEBUG level, filling the shared logging volume within six hours.

## Resolution
1. Immediate mitigation: manually delete or compress the oldest rotated log files to free emergency headroom, and immediately disable the offending DEBUG logging via config rollback.
2. Root fix: add an environment-gated safeguard preventing DEBUG-level logging from being enabled in any environment tagged `production`, regardless of config file contents.
3. Verify recovery: confirm disk utilization drops below 70% and log rotation is running on its normal schedule (check `logrotate` cron logs for the next scheduled run).

## Prevention
- Added a disk-utilization alert at 75% (not just 90%+), giving earlier warning before a full outage.
- Added a CI check that rejects any production config diff setting `LOG_LEVEL=DEBUG`.
