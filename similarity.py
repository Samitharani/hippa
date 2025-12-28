from app.ai.vector_store import vector_store

def test_search(question, patient_id):
    results = vector_store.search(question, patient_id)
    print("SIMILARITY RESULTS:", results)
    return results
