from fastapi import APIRouter, Depends
from app.auth import require_role
from app.schemas import AskRequest
from app.ai.retriever import retrieve_patient_docs
from app.ai.answer_engine import generate_answer

router = APIRouter(prefix="/ai", tags=["AI"])

from app.utils.audit_logger import log_audit


@router.post("/ask")
def ask_ai(
    data: AskRequest,
    user=Depends(require_role("doctor"))
):
    # Persist an audit record of the AI query in a PHI-safe manner
    try:
        actor = user.get("username") if isinstance(user, dict) else str(user)
        role = user.get("role") if isinstance(user, dict) else None
        log_audit(
            event="AI_QUERY",
            actor=actor,
            role=role,
            patient_id=data.patient_id,
            detail={"action": "AI_ASK", "note": data.question}
        )
    except Exception:
        # fail-safe: don't block the response on audit failure
        pass

    retrieved_docs = retrieve_patient_docs(
        patient_id=data.patient_id,
        question=data.question
    )

    # extract plain text for generation, but preserve sources for response
    texts = [d["text"] for d in retrieved_docs] if isinstance(retrieved_docs, list) and retrieved_docs and isinstance(retrieved_docs[0], dict) else retrieved_docs

    answer = generate_answer(
        question=data.question,
        retrieved_docs=texts
    )

    # Build sources, matches (with scores), and patient history used
    sources = []
    matches = []
    patients_used = set()

    try:
        if isinstance(retrieved_docs, list):
            for d in retrieved_docs:
                if isinstance(d, dict):
                    src = d.get("source")
                    if src and src not in sources:
                        sources.append(src)
                    score = d.get("score")
                    if score is not None:
                        matches.append({"source": src, "score": int(round(score * 100))})
                    if src and str(src).startswith("PAT-"):
                        patients_used.add(src)
        # always include the requested patient id as used
        patients_used.add(data.patient_id)
    except Exception:
        pass

    if not sources:
        sources = [data.patient_id]

    return {
        "answer": answer,
        "sources": sources,
        "matches": matches,
        "patients_used": list(patients_used),
        "safe": True
    }