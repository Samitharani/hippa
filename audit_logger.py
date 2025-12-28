from datetime import datetime, timezone
from app.db import audit_logs
from app.services.phi_cleaner import redact_text

# Allowed detail keys (others will be stringified but sanitized)
ALLOWED_DETAIL_KEYS = {"note", "action", "vector_id", "status"}


def _sanitize_detail(detail):
    if detail is None:
        return None
    # if dict, only keep allowed keys, redact strings
    if isinstance(detail, dict):
        out = {}
        for k, v in detail.items():
            if k in ALLOWED_DETAIL_KEYS:
                if isinstance(v, str):
                    out[k] = redact_text(v)
                else:
                    out[k] = v
        return out
    # if string, redact
    if isinstance(detail, str):
        return redact_text(detail)
    # else return stringified sanitized representation
    try:
        s = str(detail)
        return redact_text(s)
    except Exception:
        return None


def log_audit(event: str, actor: str, role: str, patient_id: str = None, detail=None):
    """Insert a standardized audit log entry while ensuring no PHI is stored.

    Fields:
      - event (str)
      - actor (str)
      - role (str)
      - patient_id (optional)
      - detail (sanitized)
      - timestamp (utc)
    """
    if not event or not actor or not role:
        raise ValueError("event, actor and role are required")

    entry = {
        "event": event,
        "actor": actor,
        "role": role,
        "patient_id": patient_id,
        "detail": _sanitize_detail(detail),
        # store timestamp as explicit UTC ISO string (e.g., 2025-12-28T05:23:25+00:00)
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # insert and return result
    return audit_logs.insert_one(entry)
