"""Chat API - Safety Copilot with Gemini function calling + fallback RAG."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services import rag
from app.services.gemini_service import chat_with_gemini

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    top_k: int = 8
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    answer: str
    route: str | None = None
    sources: list = []
    actions: list = []
    confidence: float = 0
    structured: dict | None = None
    fallback: bool = False


@router.post("/chat", summary="Safety Copilot: hybrid Gemini + RAG")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    """Gemini-powered copilot with function calling. Falls back to RAG if Gemini unavailable."""
    # Try Gemini first
    if settings.gemini_api_key:
        result = chat_with_gemini(db, req.question, req.history)
        if not result.get("fallback") and not result.get("error"):
            return {
                "answer": result["answer"],
                "route": "gemini",
                "sources": result.get("sources", []),
                "actions": result.get("actions", []),
                "confidence": result.get("confidence", 0.8),
            }

    # Fallback to existing RAG
    result = rag.answer(db, req.question, top_k=req.top_k)
    return {
        "answer": result.get("narrative", "No answer available."),
        "route": result.get("route", "rag_fallback"),
        "structured": result.get("structured"),
        "sources": [],
        "actions": [],
        "confidence": 0.5,
        "fallback": True,
    }
