from app.services.vector_db import search_vectors
from app.services.embed import embed_text   # your existing embedding function

def retrieve_context(question: str):
    q_embedding = embed_text(question)

    results = search_vectors(q_embedding)

    matches = []
    for r in results:
        matches.append({
            "vector_id": r["id"],
            "patient_id": r["patient_id"],
            "content": r["text"]
        })

    return matches
