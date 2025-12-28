from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import logging
from datetime import datetime

# DB
from app.db import patients_collection

# Auth / utils
from app.auth import require_role
from app.services.phi_cleaner import redact_text
from app.ai.vector_store import vector_store
from app.utils.activity_logger import log_activity

# Routers
from app.routes import embedding, ai_chatbot, dashboard
from app.routes.patients import router as patient_router
from app.routes.auth_routes import router as auth_router

# --------------------------------
# CREATE APP
# --------------------------------
app = FastAPI(title="Secure MedAI Backend")

logging.basicConfig(level=logging.INFO)

# --------------------------------
# MIDDLEWARE
# --------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------
# ROUTERS
# --------------------------------
app.include_router(auth_router)
app.include_router(patient_router, prefix="/api")

app.include_router(embedding.router)
app.include_router(ai_chatbot.router)
app.include_router(dashboard.router)

# admin audit routes
from app.routes.admin_audit import router as admin_audit_router
# admin_audit router already defines its own prefix 
app.include_router(admin_audit_router)


# --------------------------------
# STARTUP: ensure indexes
# --------------------------------
@app.on_event("startup")
def ensure_indexes():
    try:
        # speed up common audit queries
        from app.db import audit_logs
        audit_logs.create_index([("timestamp", -1)])
        audit_logs.create_index([("patient_id", 1)])
        audit_logs.create_index([("event", 1)])
    except Exception:
        pass

# --------------------------------
# ROOT
# --------------------------------
@app.get("/")
def root():
    return {"message": "HIPAA Backend Running"}

# --------------------------------
# PATIENT UPLOAD
# --------------------------------
@app.post("/patients/upload")
def upload_patient(payload: dict):
    text = payload.get("text", "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    patient_id = "PAT-" + str(uuid.uuid4())[:8]

    patients_collection.insert_one({
        "patient_id": patient_id,
        "raw_text": text,
        "status": "uploaded",
        "created_at": datetime.utcnow()
    })

    # ✅ LOG ACTIVITY
    log_activity(
    actor="doctor",          # later replace with user_id from JWT
    role="doctor",
    action="UPLOAD_RECEIVED"
)


    return {
        "patient_id": patient_id,
        "message": "Patient record uploaded successfully"
    }

# --------------------------------
# PHI CLEANER
# --------------------------------
@app.post("/clean-phi")
def clean_phi(payload: dict):
    text = payload.get("text", "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    cleaned_text = redact_text(text)

    log_activity(
    actor="system",
    role="system",
    action="PHI_DETECTION_COMPLETED"
)


    return {
        "cleaned_text": cleaned_text,
        "redacted_count": cleaned_text.count("[REDACTED]")
    }

# --------------------------------
# ADMIN ENDPOINTS
# --------------------------------
@app.get("/admin/health")
def admin_health(user=Depends(require_role("admin"))):
    return {
        "status": "secure",
        "vector_store_count": len(vector_store.vectors)
        if hasattr(vector_store, "vectors") else 0
    }

@app.get("/admin/stats")
def admin_stats(user=Depends(require_role("admin"))):
    return {
        "total_patients": patients_collection.count_documents({}),
        "system_status": "healthy"
    }

# --------------------------------
# DEBUG
# --------------------------------
@app.get("/debug/vectors")
def debug_vectors():
    if not hasattr(vector_store, "vectors"):
        return {"count": 0, "vectors": []}

    return {
        "count": len(vector_store.vectors),
        "vectors": [
            {
                "patient_id": v["patient_id"],
                "vector_id": v["vector_id"],
                "metadata": v.get("metadata")
            }
            for v in vector_store.vectors
        ]
    }


@app.get("/debug/test-embed")
def debug_test_embed(user=Depends(require_role("doctor"))):
    """Test embedding a short string to confirm model is available and working."""
    try:
        emb = vector_store.embed("test string")
        return {"ok": True, "len": len(emb)}
    except Exception as e:
        # return helpful, non-sensitive message
        return {"ok": False, "error": str(e)}

# --------------------------------
# RUN
# --------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
