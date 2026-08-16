from langchain_core.tools import tool

@tool
def query_recent_logs(service_name: str, minutes_back: int = 15) -> str:
    """
    Fetch recent error/warning log lines for a given service.

    Use this tool whenever the user asks about CURRENT or RECENT log activity,
    errors, or live system behavior for a specific service - not for general
    "how do we fix X" runbook questions, which should be answered from the
    retrieved documentation instead.

    Args:
        service_name: The exact service name to query, e.g. "checkout-service",
            "auth-service", "api-gateway". Must match a known service name.
        minutes_back: How many minutes of log history to fetch. Defaults to 15.

    Returns:
        A short string summarizing recent log activity for the service, or a
        message indicating no data is available for that service.
    """

    mock_log_data = {
        "checkout-service": "ERROR: connection pool exhausted (redis-pool-1) x47 in last {m}m",
        "auth-service": "WARN: token validation latency p99 340ms (baseline 80ms) over last {m}m",
        "api-gateway": "WARN: upstream 502 rate 3.2% over baseline in last {m}m",
        "notification-service": "INFO: no anomalies detected in last {m}m",
    }

    entry = mock_log_data.get(service_name)
    if entry is None:
        return f"No log data available for service '{service_name}'. Known services: {', '.join(mock_log_data)}."
    return entry.format(m=minutes_back)