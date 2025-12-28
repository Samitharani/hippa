from sentence_transformers import SentenceTransformer

# load model once
model = SentenceTransformer("all-MiniLM-L6-v2")

def generate_embedding(text: str):
    """
    Generate vector embedding for given text
    """
    embedding = model.encode(text)
    return embedding.tolist()
