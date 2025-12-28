from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from app.auth import require_role, require_any_role
from app.ai.vector_store import vector_store
from app.db import patients_collection, audit_logs
from app.services.phi_cleaner import redact_text
import logging
import re

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/embed")
def embed_patient_data(
    payload: dict,
    user=Depends(require_role("doctor"))
):
    """Embed patient text and add vector metadata. Returns 500 with clear message on failure."""
    patient_id = payload.get("patient_id")
    text = payload.get("text")

    if not patient_id or not text:
        raise HTTPException(status_code=400, detail="patient_id and text required")

    # Fetch patient document to enrich vector metadata (age, bp, past history)
    patient = patients_collection.find_one({"patient_id": patient_id})

    metadata = {
        "uploaded_by": user["username"],
        "role": user["role"]
    }

    if patient:
        # age (non-PHI numeric) — prefer direct age, otherwise attempt DOB -> year extraction
        if patient.get("age") is not None:
            metadata["age"] = patient.get("age")
        else:
            # look for a 4-digit year in text like '1980' or '/04/1980' to estimate age
            y = re.search(r"(19\d{2}|20\d{2})", " ".join(str(patient.get(k, "")) for k in ("original_text", "raw_text", "cleaned_text", "notes")))
            if y:
                try:
                    birth_year = int(y.group(1))
                    from datetime import datetime as _dt
                    metadata["age"] = _dt.utcnow().year - birth_year
                except Exception:
                    pass

        # search for BP and Past Medical History in stored text fields
        text_fields = " ".join(str(patient.get(k, "")) for k in ("original_text", "raw_text", "cleaned_text", "chief_complaint", "notes"))

        # current BP (e.g., 'BP: 120/80' or 'blood pressure 120/80')
        m = re.search(r"\b(?:BP|Blood Pressure)[: ]+\s*(\d{2,3}/\d{2,3})", text_fields, re.IGNORECASE)
        if m:
            metadata["bp"] = m.group(1)

        # Past Medical History — multiple heuristics
        # 1) explicit 'Past Medical History: ...'
        m2 = re.search(r"Past Medical History:\s*(.+?)(?:\n|$)", text_fields, re.IGNORECASE)
        if m2:
            metadata["past_history"] = m2.group(1).strip()
        else:
            # 2) 'History of X' or 'Hx: X' patterns
            m3 = re.search(r"(?:History of|Hx[:\s]+)\s*([A-Za-z0-9\- ,/]+?)(?:[.,\n]|$)", text_fields, re.IGNORECASE)
            if m3:
                metadata["past_history"] = m3.group(1).strip()
            else:
                # 3) keyword based fallback (e.g., 'hypertension', 'diabetes')
                keywords = []
                for kw in ("hypertension", "diabetes", "asthma", "copd", "cancer", "stroke"):
                    if re.search(rf"\b{kw}\b", text_fields, re.IGNORECASE):
                        keywords.append(kw)
                if keywords:
                    metadata["past_history"] = ", ".join(keywords)

    try:
        vector_id = vector_store.store(
            patient_id=patient_id,
            text=text,
            metadata=metadata
        )
    except Exception as e:
        # log and return a 500 with a short message
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

    patients_collection.update_one(
        {"patient_id": patient_id},
        {
            "$set": {
                "cleaned_text": text,
                "vector_id": vector_id,
                "status": "embedded"
            }
        }
    )

    # ✅ AUDIT LOG — INSIDE FUNCTION (standardized)
    from app.utils.audit_logger import log_audit
    log_audit(event="VECTOR_EMBEDDED", actor=user["username"], role=user["role"], patient_id=patient_id)

    return {
        "vector_id": vector_id,
        "status": "embedded"
    }


@router.post("/reembed")
def reembed_patient(
    payload: dict,
    user=Depends(require_role("doctor"))
):
    """Re-run embedding for an existing patient to refresh vector metadata.
    Payload: {"patient_id": "PAT-..."}
    Protected: doctor role required."""
    patient_id = payload.get("patient_id")

    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id required")

    patient = patients_collection.find_one({"patient_id": patient_id})
    if not patient:
        raise HTTPException(status_code=404, detail="patient not found")

    # build the same metadata extraction logic used by /embed
    metadata = {"uploaded_by": user["username"], "role": user["role"]}

    # age
    if patient.get("age") is not None:
        metadata["age"] = patient.get("age")
    else:
        y = re.search(r"(19\d{2}|20\d{2})", " ".join(str(patient.get(k, "")) for k in ("original_text", "raw_text", "cleaned_text", "notes")))
        if y:
            try:
                birth_year = int(y.group(1))
                from datetime import datetime as _dt
                metadata["age"] = _dt.utcnow().year - birth_year
            except Exception:
                pass

    text_fields = " ".join(str(patient.get(k, "")) for k in ("original_text", "raw_text", "cleaned_text", "chief_complaint", "notes"))

    m = re.search(r"\b(?:BP|Blood Pressure)[: ]+\s*(\d{2,3}/\d{2,3})", text_fields, re.IGNORECASE)
    if m:
        metadata["bp"] = m.group(1)

    m2 = re.search(r"Past Medical History:\s*(.+?)(?:\n|$)", text_fields, re.IGNORECASE)
    if m2:
        metadata["past_history"] = m2.group(1).strip()
    else:
        m3 = re.search(r"(?:History of|Hx[:\s]+)\s*([A-Za-z0-9\- ,/]+?)(?:[.,\n]|$)", text_fields, re.IGNORECASE)
        if m3:
            metadata["past_history"] = m3.group(1).strip()
        else:
            # keyword fallback
            keywords = []
            for kw in ("hypertension", "diabetes", "asthma", "copd", "cancer", "stroke"):
                if re.search(rf"\b{kw}\b", text_fields, re.IGNORECASE):
                    keywords.append(kw)
            if keywords:
                metadata["past_history"] = ", ".join(keywords)

    # use cleaned_text if available, otherwise raw_text
    text_for_embed = patient.get("cleaned_text") or patient.get("raw_text") or patient.get("original_text") or ""

    try:
        vector_id = vector_store.store(patient_id=patient_id, text=text_for_embed, metadata=metadata)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-embed failed: {str(e)}")

    patients_collection.update_one({"patient_id": patient_id}, {"$set": {"vector_id": vector_id, "status": "embedded"}})

    from app.utils.audit_logger import log_audit
    log_audit(event="VECTOR_REEMBEDDED", actor=user["username"], role=user["role"], patient_id=patient_id)

    return {"vector_id": vector_id, "status": "embedded"}


@router.post("/analysis")
def ai_analysis(
    payload: dict = {},
    user=Depends(require_any_role("doctor", "nurse"))
):
    """Run a rule-based AI analysis on the latest embedded patient (or provided patient_id).
    - Only analyses de-identified / cleaned clinical text.
    - If `patient_id` is provided it must match the latest embedded patient to ensure we analyze most recent report.
    Output (JSON):
      { clinical_risk_explanation, possible_conditions, red_flags, general_recommendations }
    """
    patient_id = payload.get("patient_id") if isinstance(payload, dict) else None

    # find latest embedded
    latest = patients_collection.find_one({"status": "embedded"}, sort=[("created_at", -1)])
    if not latest:
        raise HTTPException(status_code=404, detail="No embedded patient available for analysis")

    if patient_id and patient_id != latest.get("patient_id"):
        raise HTTPException(status_code=400, detail="Analysis allowed only on the latest embedded patient record")

    patient = latest

    # use cleaned_text only
    clinical_text = patient.get("cleaned_text") or ""
    if not clinical_text.strip():
        raise HTTPException(status_code=400, detail="No de-identified clinical text available for analysis")

    # ensure PHI removed
    safe_text = redact_text(clinical_text)

    # RULE-BASED ANALYSIS (deterministic, no PHI exposure)
    txt = safe_text.lower()

    # red flags detection
    red_flags = []
    for kw in ("chest pain", "shortness of breath", "syncope", "hemoptysis", "severe bleeding", "loss of consciousness", "sudden weakness"):
        if kw in txt:
            red_flags.append(kw)

    # possible conditions heuristics
    possible_conditions = set()
    if "chest pain" in txt or "radiating" in txt or "left arm" in txt:
        possible_conditions.add("Acute coronary syndrome / myocardial ischemia")
    if re.search(r"fever|sepsis|infection", txt):
        possible_conditions.add("Infectious process / sepsis")
    if re.search(r"shortness of breath|dyspnea|sob", txt):
        possible_conditions.add("Heart failure or pulmonary embolism")
    if re.search(r"hypertension|history of hypertension|htn", txt):
        possible_conditions.add("Hypertensive disease — cardiovascular risk")
    if re.search(r"diabetes|dm\b", txt):
        possible_conditions.add("Diabetes-related complications")

    # clinical risk explanation (simple heuristic)
    risk = "low"
    if red_flags or re.search(r"unstable|critical|severe|hemodynamic|shock", txt):
        risk = "high"
    elif re.search(r"concern|watch|monitor|moderate", txt) or len(possible_conditions) >= 2:
        risk = "medium"

    clinical_risk_explanation = (
        f"This case is assessed as {risk.upper()} risk based on present red flags and clinical features."
    )

    # general recommendations (templated)
    recommendations = []
    if "chest pain" in txt or "left arm" in txt:
        recommendations.append("Immediate ECG and cardiac enzyme testing; consider urgent cardiology evaluation.")
    if "shortness of breath" in txt:
        recommendations.append("Evaluate oxygenation, chest imaging, and consider pulmonary embolism workup if indicated.")
    if "fever" in txt or "sepsis" in txt:
        recommendations.append("Obtain blood cultures, start empiric antibiotics as per local protocol, and monitor vitals closely.")

    # default recommendations
    if not recommendations:
        recommendations.append("Perform focused clinical assessment and baseline investigations (vitals, ECG, basic labs) as clinically indicated.")

    result = {
        "clinical_risk_explanation": clinical_risk_explanation,
        "possible_conditions": list(possible_conditions) or ["No specific likely conditions identified from de-identified text"],
        "red_flags": red_flags or ["No immediate red flags detected"],
        "general_recommendations": recommendations
    }

    # Audit — standardized
    try:
        from app.utils.audit_logger import log_audit
        log_audit(event="AI_ANALYSIS", actor=user["username"], role=user["role"], patient_id=patient.get("patient_id"))
    except Exception:
        pass

    return result
