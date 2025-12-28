from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from app.auth import get_current_user

from fastapi import APIRouter, Depends, HTTPException
from app.db import patients_collection
from app.auth import require_role

router = APIRouter(prefix="/patients", tags=["Patients"])

from app.db import (
    patients_collection,
    users_collection,
    audit_logs
)
from app.ai.vector_store import vector_store
from app.auth import require_role

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)

# -------------------------------
# 📊 ADMIN STATS
# -------------------------------
@router.get("/stats")
def dashboard_stats(user=Depends(get_current_user)):

    total_users = users_collection.count_documents({})
    doctors = users_collection.count_documents({"role": "doctor"})
    nurses = users_collection.count_documents({"role": "nurse"})
    admins = users_collection.count_documents({"role": "admin"})

    total_vectors = len(vector_store.vectors)
    cleaned_records = patients_collection.count_documents({"status": "embedded"})
    pending_phi = patients_collection.count_documents({"status": "uploaded"})


    failed_logins = audit_logs.count_documents({
        "detail.action": "LOGIN_FAILED"
    })

    total_events = audit_logs.count_documents({})

    return {
        "total_users": total_users,
        "doctors": doctors,
        "nurses": nurses,
        "admins": admins,
        "cleaned_records": cleaned_records,
        "encrypted_vectors": total_vectors,
        "pending_phi": pending_phi,
        "failed_logins": failed_logins,
        "total_events": total_events
    }


# -------------------------------
# 🧾 RECENT ACTIVITY
@router.get("/activity")
def recent_activity(user=Depends(get_current_user)):


    logs = audit_logs.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).limit(8)

    def extract_action(log):
        # action may be nested in detail.action (new schema) or top-level 'action' (legacy)
        if isinstance(log.get('detail'), dict):
            return log.get('detail').get('action') or log.get('event')
        return log.get('action') or log.get('event')

    def as_iso_timestamp(ts):
        # Normalize various timestamp representations to an ISO string with timezone info (UTC)
        from datetime import datetime, timezone
        if isinstance(ts, datetime):
            # ensure timezone-aware and return UTC iso
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.astimezone(timezone.utc).isoformat()
        if isinstance(ts, str):
            # already a string — if it lacks timezone info append 'Z' to indicate UTC
            # simple heuristic: if contains 'Z' or '+' or timezone offset already, return as-is
            if 'Z' in ts or '+' in ts or '-' in ts[10:]:
                return ts
            return ts + 'Z'
        return str(ts)

    return [
        {
            "actor": log.get("actor", "system"),
            "event": extract_action(log) or "",
            "timestamp": as_iso_timestamp(log.get("timestamp"))
        }
        for log in logs
    ]

# ---------------------------------
# 🔍 GET LATEST PATIENT (AUTO UPDATE)
# ---------------------------------
@router.get("/latest")
def get_latest_patient(user=Depends(require_role("doctor"))):
    patient = patients_collection.find_one(
        {},
        sort=[("created_at", -1)],
        projection={"_id": 0}
    )

    if not patient:
        raise HTTPException(status_code=404, detail="No patient found")

    return patient


# ---------------------------------
# 🔍 GET PATIENT BY ID
# ---------------------------------
@router.get("/{patient_id}")
def get_patient(patient_id: str, user=Depends(require_role("doctor"))):
    patient = patients_collection.find_one(
        {"patient_id": patient_id},
        {"_id": 0}
    )

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    return patient


# ---------------------------------
# 🕒 PATIENT TIMELINE
# ---------------------------------
@router.get("/{patient_id}/history")
def patient_history(patient_id: str, user=Depends(require_role("doctor"))):
    records = patients_collection.find(
        {"patient_id": patient_id},
        {"_id": 0}
    ).sort("created_at", 1)

    return list(records)