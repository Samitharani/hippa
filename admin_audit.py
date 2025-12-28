from fastapi import APIRouter, Depends, HTTPException
from app.auth import require_role
from app.db import audit_logs, users_collection, settings_collection
from datetime import datetime
import csv
from io import StringIO

router = APIRouter(prefix="/admin/audit", tags=["Admin"])


@router.get("")
def list_audit_logs(
    event: str = None,
    actor: str = None,
    patient_id: str = None,
    role: str = None,
    from_ts: str = None,
    to_ts: str = None,
    q: str = None,
    status: str = None,
    limit: int = 50,
    skip: int = 0,
    user=Depends(require_role("admin"))
):
    """List audit logs with filters, search and pagination"""
    query = {}
    if event:
        query["event"] = event
    if actor:
        query["actor"] = actor
    if patient_id:
        query["patient_id"] = patient_id
    if role:
        query["role"] = role

    # text search across common fields
    if q:
        query["$or"] = [
            {"event": {"$regex": q, "$options": "i"}},
            {"actor": {"$regex": q, "$options": "i"}},
            {"role": {"$regex": q, "$options": "i"}},
            {"detail.action": {"$regex": q, "$options": "i"}},
            {"detail.note": {"$regex": q, "$options": "i"}}
        ]

    # status filter
    if status:
        # map 'Error' to failed/error variants for compatibility with UI
        st = status.strip().lower()
        if st == 'error':
            query["detail.status"] = {"$in": ["Failed", "failed", "FAILED", "Error", "error", "ERROR"]}
        else:
            # match various casings
            query["detail.status"] = {"$in": [status, status.lower(), status.upper(), status.capitalize()]}

    if from_ts or to_ts:
        time_query = {}
        try:
            if from_ts:
                time_query["$gte"] = datetime.fromisoformat(from_ts)
            if to_ts:
                time_query["$lte"] = datetime.fromisoformat(to_ts)
            query["timestamp"] = time_query
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
    total = audit_logs.count_documents(query)
    cursor = audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)

    events = []
    for d in cursor:
        d["_id"] = str(d.get("_id"))
        # do not include raw detail that might have PHI; detail is already sanitized by logger
        events.append({
            "_id": d["_id"],
            "event": d.get("event"),
            "actor": d.get("actor"),
            "role": d.get("role"),
            "patient_id": d.get("patient_id"),
            "detail": d.get("detail"),
            "timestamp": d.get("timestamp")
        })

    return {"total": total, "events": events, "limit": limit, "skip": skip}


@router.get("/events")
def distinct_events(user=Depends(require_role("admin"))):
    keys = audit_logs.distinct("event")
    return {"events": keys}


@router.post("/export")
def export_audit_logs(filters: dict = {}, user=Depends(require_role("admin"))):
    # Reuse list logic but return CSV
    # Accepts filters in JSON body
    query = {}
    for k in ("event", "actor", "patient_id", "role"):
        if filters.get(k):
            query[k] = filters.get(k)

    # q and status support in export as well
    if filters.get("q"):
        q = filters.get("q")
        query["$or"] = [
            {"event": {"$regex": q, "$options": "i"}},
            {"actor": {"$regex": q, "$options": "i"}},
            {"role": {"$regex": q, "$options": "i"}},
            {"detail.action": {"$regex": q, "$options": "i"}},
            {"detail.note": {"$regex": q, "$options": "i"}}
        ]

    if filters.get("status"):
        st = filters.get("status").strip().lower()
        if st == 'error':
            query["detail.status"] = {"$in": ["Failed", "failed", "FAILED", "Error", "error", "ERROR"]}
        else:
            query["detail.status"] = {"$in": [filters.get("status"), filters.get("status").lower(), filters.get("status").upper(), filters.get("status").capitalize()]}

    if filters.get("from_ts") or filters.get("to_ts"):
        time_query = {}
        try:
            if filters.get("from_ts"):
                time_query["$gte"] = datetime.fromisoformat(filters.get("from_ts"))
            if filters.get("to_ts"):
                time_query["$lte"] = datetime.fromisoformat(filters.get("to_ts"))
            query["timestamp"] = time_query
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")

    cursor = audit_logs.find(query).sort("timestamp", -1).limit(10000)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "event", "actor", "role", "patient_id", "detail"])

    for d in cursor:
        writer.writerow([
            d.get("timestamp"),
            d.get("event"),
            d.get("actor"),
            d.get("role"),
            d.get("patient_id"),
            str(d.get("detail"))
        ])

    return {"csv": output.getvalue()}


@router.get("/stats")
def audit_stats(user=Depends(require_role("admin"))):
    total = audit_logs.count_documents({})
    # counts by event
    pipeline = [
        {"$group": {"_id": "$event", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    by_event = list(audit_logs.aggregate(pipeline))

    # counts by status (detail.status) - be permissive about casing
    success = audit_logs.count_documents({"detail.status": {"$in": ["Success", "success", "SUCCESS"]}})
    warning = audit_logs.count_documents({"detail.status": {"$in": ["Warning", "warning", "WARNING"]}})
    failed = audit_logs.count_documents({"detail.status": {"$in": ["Failed", "failed", "FAILED", "Error", "error", "ERROR"]}})

    return {"total": total, "by_event": by_event, "success": success, "warning": warning, "failed": failed}


@router.get("/roles")
def roles_stats(user=Depends(require_role("admin"))):
    # compute distinct roles and counts
    roles = users_collection.distinct("role")
    total_roles = len(roles)
    # include 'auditor' as a known system role
    system_role_set = {"doctor", "nurse", "admin", "auditor"}
    system_roles = sum(1 for r in roles if isinstance(r, str) and r.lower() in system_role_set)
    custom_roles = total_roles - system_roles

    # canonical descriptions & permissions for known roles
    ROLE_META = {
        "doctor": {
            "description": "Access patient records and AI tools",
            "permissions": "View, Create"
        },
        "nurse": {
            "description": "Upload and view patient data",
            "permissions": "View, Upload"
        },
        "admin": {
            "description": "Full system access",
            "permissions": "All Permissions"
        },
        "auditor": {
            "description": "Read-only audit access",
            "permissions": "View Logs"
        }
    }

    role_counts = []
    for r in roles:
        cnt = users_collection.count_documents({"role": r})
        meta = ROLE_META.get(str(r).lower(), {})
        role_counts.append({
            "role": r,
            "count": cnt,
            "description": meta.get("description", "Custom role"),
            "permissions": meta.get("permissions", "Custom")
        })

    return {"total_roles": total_roles, "system_roles": system_roles, "custom_roles": custom_roles, "roles": role_counts}


# ---------------------------------
# ⚙️ System Settings (persisted)
# ---------------------------------
@router.get("/settings")
def get_settings(user=Depends(require_role("admin"))):
    """Return current system settings or defaults"""
    defaults = {
        "phi_sensitivity": "Medium",
        "session_timeout": "30 minutes",
        "audit_log_retention": "90 days",
        "student_mode": "Disabled"
    }

    s = settings_collection.find_one({"_id": "system"})
    if not s:
        return defaults

    # merge defaults with stored values
    out = defaults.copy()
    out.update({
        k: s.get(k, v) for k, v in defaults.items()
    })
    return out


@router.post("/settings")
def set_settings(payload: dict, user=Depends(require_role("admin"))):
    """Persist system settings (upsert)"""
    # validate keys and simple value checks
    allowed_phi = {"Low", "Medium", "High"}
    allowed_timeouts = {"15 minutes", "30 minutes", "60 minutes"}
    allowed_retention = {"30 days", "90 days", "1 year"}
    allowed_student = {"Disabled", "Enabled"}

    phi = payload.get("phi_sensitivity")
    if phi and phi not in allowed_phi:
        raise HTTPException(status_code=400, detail="Invalid PHI sensitivity")

    timeout = payload.get("session_timeout")
    if timeout and timeout not in allowed_timeouts:
        raise HTTPException(status_code=400, detail="Invalid session timeout")

    retention = payload.get("audit_log_retention")
    if retention and retention not in allowed_retention:
        raise HTTPException(status_code=400, detail="Invalid audit retention")

    student = payload.get("student_mode")
    if student and student not in allowed_student:
        raise HTTPException(status_code=400, detail="Invalid student mode")

    settings_doc = {
        "_id": "system",
        "phi_sensitivity": phi or "Medium",
        "session_timeout": timeout or "30 minutes",
        "audit_log_retention": retention or "90 days",
        "student_mode": student or "Disabled",
        "updated_at": datetime.utcnow()
    }

    settings_collection.update_one({"_id": "system"}, {"$set": settings_doc}, upsert=True)

    return {"ok": True, "settings": settings_doc}