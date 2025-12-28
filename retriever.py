from app.ai.vector_store import vector_store
from app.db import patients_collection

def retrieve_patient_docs(patient_id: str, question: str, top_k: int = 3):
    """
    Retrieve patient record chunks from vector DB.

    Returns a list of dicts: {"text": ..., "source": <vector_id or patient_id>}
    """

    # use similarity search over patient's vectors for the question
    results = vector_store.search_similar(patient_id, question, top_k)

    docs = []
    for r in results:
        # r now includes a 'score' key thanks to vector_store.search_similar
        text = r.get("metadata", {}).get("text")
        src = r.get("vector_id") or r.get("metadata", {}).get("vector_id")
        source = src or patient_id
        score = r.get("score", None)
        if text:
            docs.append({"text": text, "source": source, "score": score})

    # If no vectors found, fall back to the patient's latest embedded/cleaned text
    if not docs:
        try:
            patient = patients_collection.find_one({"patient_id": patient_id})
            if patient:
                text = patient.get("cleaned_text") or patient.get("raw_text") or patient.get("original_text")
                if text:
                    docs.append({"text": text, "source": patient_id, "score": None})
        except Exception:
            # don't fail retrieval due to DB errors — return empty list
            pass

    return docs
