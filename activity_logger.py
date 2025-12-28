from datetime import datetime, timezone
from app.utils.audit_logger import log_audit


def log_activity(actor, role, action, status="success", ip="127.0.0.1"):
    # Normalize status to Title case (e.g., 'Success', 'Warning', 'Failed') for consistent UI and aggregation
    try:
        status_clean = str(status).strip().capitalize()
    except Exception:
        status_clean = "Success"

    # Use standardized audit logger and keep action/status as sanitized detail
    detail = {"action": action, "status": status_clean, "ip": ip}
    return log_audit(event="ACCESS_EVENT", actor=actor, role=role, detail=detail)
