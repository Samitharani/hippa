from fastapi import APIRouter, UploadFile, File, Form, Depends,HTTPException
from datetime import datetime
from app.db import patients_collection, audit_logs
from app.auth import require_role, require_any_role
import re


router = APIRouter(prefix="/patients")





@router.post("/upload")
async def upload_patient_record(
    patient_id: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(require_role("doctor"))
):
    # 1️⃣ Read text file
    text = (await file.read()).decode("utf-8")

    # 2️⃣ Store ORIGINAL TEXT in MongoDB
    patients_collection.insert_one({
        "patient_id": patient_id,
        "raw_text": text,
        "uploaded_by": user["username"],
        "status": "uploaded",
        "created_at": datetime.utcnow()
    })

    print("🟢 INSERTING PATIENT:", patient_id)

    return {
        "message": "Patient record uploaded",
        "patient_id": patient_id
    }

# ---------------------------
# GET LATEST PATIENT
# ---------------------------
@router.get("/latest")
def get_latest_patient(limit: int = 1, user=Depends(require_any_role("doctor", "nurse"))):
    """Return the latest embedded patient record(s) (default 1). The response is
    sanitized to remove PHI and enriched with non-PHI clinical fields that the
    frontend expects (case_id, age_group, primary_diagnosis, medications,
    timeline). Vector metadata is preferred when available (non-PHI fields like
    age, bp, past_history) with MongoDB as a fallback.
    """
    cursor = patients_collection.find(
        {"status": "embedded"},
        sort=[("created_at", -1)]
    ).limit(limit)

    results = []

    for patient in cursor:
        pid = patient.get("patient_id")

        # map id
        patient["_id"] = str(patient["_id"])

        # remove PHI
        for phi_field in ("raw_text", "original_text", "patient_name", "cleaned_text"):
            patient.pop(phi_field, None)

        # build non-PHI case fields
        case = {
            "case_id": patient.get("vector_id") or patient.get("patient_id"),
            "patient_id": patient.get("patient_id"),
            "created_at": patient.get("created_at"),
        }

        # age (numeric) + age_group (prefer vector metadata later)
        age = patient.get("age")
        if age is not None:
            case["age"] = age
            if isinstance(age, int):
                if age < 18:
                    case["age_group"] = "pediatric"
                elif age >= 65:
                    case["age_group"] = "senior"
                else:
                    case["age_group"] = "adult"

        # Extract BP and Past Medical History from available text fields (Mongo fallback)
        text_fields = " ".join(str(patient.get(k, "")) for k in ("original_text", "raw_text", "cleaned_text", "chief_complaint", "notes"))

        # current BP (if present in mongo doc)
        bp_match = re.search(r"\b(?:BP|Blood Pressure)[: ]+\s*(\d{2,3}/\d{2,3})", text_fields, re.IGNORECASE)
        if bp_match:
            case["current_bp"] = bp_match.group(1)
        else:
            case["current_bp"] = None

        # past medical history (simple capture)
        ph_match = re.search(r"Past Medical History:\s*(.+?)(?:\n|$)", text_fields, re.IGNORECASE)
        if ph_match:
            case["past_history"] = ph_match.group(1).strip()
        else:
            # fallback to metadata stored in patient notes
            case["past_history"] = patient.get("past_history") or patient.get("notes") or None

        # primary diagnosis (best-effort heuristic)
        text = patient.get("chief_complaint") or ""
        # look for a Diagnosis field in metadata if available
        diag = None
        if "diagnosis" in patient:
            diag = patient.get("diagnosis")
        else:
            m = re.search(r"Primary Diagnosis:\s*(.+)", text, re.IGNORECASE)
            if m:
                diag = m.group(1).strip()
        case["primary_diagnosis"] = diag

        # medications (heuristic: look for 'mg' or 'dose' in available text fields)
        meds = []
        search_text = ""
        # try to use cleaned_text stored under a different key (safe) if present in doc metadata
        if patient.get("notes"):
            search_text = patient.get("notes")
        # fallback: try any remaining short fields
        if not search_text:
            search_text = " ".join(str(patient.get(k, "")) for k in ["chief_complaint"]) or ""

        for line in re.split(r"[\n\r]+", search_text):
            if re.search(r"\b\d+\s*mg\b|\bDose\b|\bdose\b|once daily|twice daily|tablet", line, re.IGNORECASE):
                # very small parser: name then dosage
                name = line.strip()
                meds.append({"name": name, "dose": "", "frequency": ""})

        case["medications"] = meds

        # timeline: include upload and embedding event
        timeline = []
        if patient.get("created_at"):
            timeline.append({
                "date": patient.get("created_at"),
                "event": "Clinical record uploaded & de-identified"
            })

        # find embed audit log for nicer message
        embed_log = None
        try:
            embed_log = audit_logs.find_one({"patient_id": pid, "event": "VECTOR_EMBEDDED"}, sort=[("timestamp", -1)])
        except Exception:
            embed_log = None

        if embed_log and embed_log.get("timestamp"):
            timeline.append({
                "date": embed_log.get("timestamp"),
                "event": "Indexing completed (vector embedded)"
            })

        case["timeline"] = timeline

        # risk_level simple heuristic
        risk = "low"
        txt_for_risk = search_text.lower()
        if any(k in txt_for_risk for k in ("critical", "icu", "unstable", "hemodynamic")):
            risk = "high"
        elif any(k in txt_for_risk for k in ("watch", "monitor", "concern")):
            risk = "medium"
        case["risk_level"] = risk

        # --- Prefer vector metadata when available ---
        try:
            vecs = vector_store.search(pid, top_k=1)
            if vecs:
                vmeta = vecs[0].get("metadata", {})
                # prefer non-PHI numeric age from vector metadata
                if vmeta.get("age") is not None:
                    case["age"] = vmeta.get("age")
                    # recompute age_group if numeric
                    try:
                        a = int(vmeta.get("age"))
                        if a < 18:
                            case["age_group"] = "pediatric"
                        elif a >= 65:
                            case["age_group"] = "senior"
                        else:
                            case["age_group"] = "adult"
                    except Exception:
                        pass

                if vmeta.get("bp"):
                    case["current_bp"] = vmeta.get("bp")
                if vmeta.get("past_history"):
                    case["past_history"] = vmeta.get("past_history")
        except Exception:
            # if vector store unavailable, silently continue with Mongo values
            pass

        # merge sanitized patient fields and case
        patient_response = {**case}
        results.append(patient_response)

    if not results:
        raise HTTPException(status_code=404, detail="No embedded patient found")

    # if single result, return object (keeps frontend unchanged)
    if limit == 1:
        return results[0]

    return results


@router.get("/latest/debug")
def get_latest_patient_debug(user=Depends(require_role("doctor"))):
    """Return the latest embedded patient and both data sources (Mongo doc and vector metadata)
    for debugging. This endpoint is protected by `doctor` role.
    """
    patient = patients_collection.find_one({"status": "embedded"}, sort=[("created_at", -1)])
    if not patient:
        raise HTTPException(status_code=404, detail="No embedded patient found")

    pid = patient.get("patient_id")

    # sanitize patient doc (remove PHI)
    sanitized = {k: v for k, v in patient.items() if k not in ("raw_text", "original_text", "patient_name", "cleaned_text")}
    sanitized["_id"] = str(sanitized.get("_id"))

    vec_meta = None
    try:
        vecs = vector_store.search(pid, top_k=1)
        if vecs:
            vec_meta = vecs[0].get("metadata")
    except Exception:
        vec_meta = None

    return {"mongo": sanitized, "vector_metadata": vec_meta}

