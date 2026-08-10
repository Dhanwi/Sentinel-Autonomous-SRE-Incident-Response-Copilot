---
title: SSL/TLS Certificate Expiration on API Gateway
service: api-gateway
severity: critical
tags: [ssl, tls, certificate, api-gateway, outage]
last_updated: 2026-01-19
---

# SSL/TLS Certificate Expiration — api-gateway

## Symptoms
- All external clients report `NET::ERR_CERT_DATE_INVALID` or equivalent SSL handshake failures.
- Internal service-to-service traffic (which bypasses the public cert) continues to work normally — this is the key signal that narrows the problem to the edge/gateway layer specifically.
- Complete external outage despite all backend services reporting healthy.

## Diagnosis
1. Confirm expiry immediately: `openssl s_client -connect api.example.com:443 -servername api.example.com | openssl x509 -noout -dates`.
2. Check the certificate renewal automation (cert-manager / ACME client) logs for failed renewal attempts in the preceding 30 days — expiration is almost never a surprise, it's a failed automated renewal that went unnoticed.
3. Common underlying cause: DNS-01 or HTTP-01 challenge failing silently due to a changed DNS provider API token or a firewall rule blocking the ACME challenge path.

## Root Cause (most recent occurrence)
cert-manager's DNS-01 challenge began failing three weeks prior after a DNS provider API token rotation was not propagated to the cert-manager secret, and renewal failure alerts were routed to a Slack channel nobody was monitoring.

## Resolution
1. Immediate mitigation: manually issue a short-lived certificate via the CA's dashboard and apply it directly to the gateway's TLS secret to restore service within minutes.
2. Root fix: update the DNS provider API token in the cert-manager secret; force a manual renewal (`cert-manager.io/issue-temporary-certificate` trigger) and confirm success.
3. Verify recovery: re-run the `openssl s_client` check above and confirm `notAfter` is now 60+ days out.

## Prevention
- Renewal failure alerts rerouted to PagerDuty (not just Slack) starting 20 days before expiry, escalating daily thereafter.
- Added a synthetic monitor that independently checks cert expiry daily, decoupled from cert-manager's own self-reporting.