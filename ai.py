from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.rag import retrieve_contexts, generate_answer

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/ask")
def ask_ai(payload: dict, db: Session = Depends(get_db)):
    question = payload.get("question", "")

    contexts = retrieve_contexts(question, db)
    answer = generate_answer(question, contexts)

    return {
        "question": question,
        "answer": answer,
        "contexts_used": len(contexts)
    }
