import logging
from sentence_transformers import SentenceTransformer
import uuid

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        # load model defensively — if loading fails, keep None and log error
        try:
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            logger.exception("Failed to load sentence transformer model")
            self.model = None

        self.vectors = []  # in-memory Vector DB

    def embed(self, text: str):
        if not self.model:
            raise RuntimeError("Embedding model not available. Check server logs for load error.")

        try:
            emb = self.model.encode(text)
            # ensure list output for JSON-serializable storage
            return emb.tolist() if hasattr(emb, "tolist") else list(emb)
        except Exception as e:
            logger.exception("Error while computing embedding")
            raise RuntimeError("Embedding generation failed: %s" % str(e))

    def store(self, patient_id: str, text: str, metadata: dict):
        embedding = self.embed(text)
        vector_id = f"VEC-{uuid.uuid4().hex[:10]}"

        record = {
            "vector_id": vector_id,
            "patient_id": patient_id,
            "embedding": embedding,
            "metadata": {
                **metadata,
                "text": text
            }
        }

        self.vectors.append(record)
        return vector_id

    def search(self, patient_id: str, top_k=3):
        """Return the top_k vectors for a patient (by insertion order fallback).
        Backwards compatible helper.
        """
        return [
            v for v in self.vectors
            if v["patient_id"] == patient_id
        ][:top_k]

    def _cosine_sim(self, a, b):
        # simple cosine similarity for two equal-length lists
        try:
            dot = sum(x * y for x, y in zip(a, b))
            la = sum(x * x for x in a) ** 0.5
            lb = sum(y * y for y in b) ** 0.5
            if la == 0 or lb == 0:
                return 0.0
            return dot / (la * lb)
        except Exception:
            return 0.0

    def search_similar(self, patient_id: str, query_text: str, top_k: int = 3):
        """Embed the query_text and return top_k most similar vectors for the patient_id by cosine similarity."""
        if not self.model:
            raise RuntimeError("Embedding model not available for similarity search")

        q_emb = self.embed(query_text)

        # compute similarity for vectors matching patient_id
        candidates = [v for v in self.vectors if v["patient_id"] == patient_id]
        scored = []
        for v in candidates:
            emb = v.get("embedding")
            if not emb:
                continue
            score = self._cosine_sim(q_emb, emb)
            scored.append((score, v))

        # sort descending by score and return top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for s, v in scored[:top_k]:
            # return a shallow copy with score for downstream attribution
            rec = dict(v)
            rec["score"] = s
            results.append(rec)
        return results



# ✅ SINGLETON INSTANCE (IMPORTANT)
vector_store = VectorStore()


# 🔍 DEBUG (optional – remove later)
if __name__ == "__main__":
    print("📦 TOTAL VECTORS STORED:", len(vector_store.vectors))
    if vector_store.vectors:
        print("🧠 LAST VECTOR:", vector_store.vectors[-1])
