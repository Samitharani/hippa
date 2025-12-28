from fastapi import APIRouter, UploadFile, File, Form, Depends
from datetime import datetime
from app.db import patients_collection
from app.auth import require_role
import re


router = APIRouter(prefix="/patients", tags=["Patients"])


# 🔹 FIELD EXTRACTION
def extract_fields(text: str):
    return {
        "patient_name": re.search(r"Patient Name:\s*([A-Za-z ]+)", text, re.IGNORECASE),
        "age": re.search(r"Age:\s*(\d+)", text, re.IGNORECASE),
        "gender": re.search(r"Gender:\s*(Male|Female|Other)", text, re.IGNORECASE),
        "chief_complaint": re.search(r"Chief Complaint:\s*([^A-Z]+)", text, re.IGNORECASE),
    }


@router.post("/upload")
async def upload_patient_record(
    patient_id: str = Form(...),
    file: UploadFile = File(...),
    user=Depends(require_role("doctor"))
):
    # 1️⃣ Read uploaded file
    text = (await file.read()).decode("utf-8")

    # 2️⃣ Extract dashboard fields
    fields = extract_fields(text)

    # 🔍 DEBUG (KEEP FOR NOW)
    print("🧪 EXTRACTED FIELDS:", {
        k: v.group(1) if v else None for k, v in fields.items()
    })

    # 3️⃣ Store in MongoDB
    patients_collection.insert_one({
        "patient_id": patient_id,

        "patient_name": fields["patient_name"].group(1) if fields["patient_name"] else None,
        "age": int(fields["age"].group(1)) if fields["age"] else None,
        "gender": fields["gender"].group(1) if fields["gender"] else None,
        "chief_complaint": fields["chief_complaint"].group(1) if fields["chief_complaint"] else None,

        "original_text": text,
        "uploaded_by": user["username"],
        "status": "uploaded",
        "created_at": datetime.utcnow()
    })

    print("🟢 INSERTED PATIENT:", patient_id)

    return {
        "message": "Patient record uploaded",
        "patient_id": patient_id
    }
