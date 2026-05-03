"""
Chat Router
Handles streaming LLM responses via LangGraph agent.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.services.agent import BundlbiteAgent
import json

router = APIRouter()
agent = BundlbiteAgent()


class ChatRequest(BaseModel):
    message: str
    session_id: str
    location: dict = {"lat": 12.9716, "lng": 77.5946}  # Default: Bangalore


@router.post("/")
async def chat(req: ChatRequest):
    """
    Accepts group order text and streams back AI responses.
    The LangGraph agent parses, fetches, ranks, and returns baskets.
    """
    async def event_stream():
        async for chunk in agent.stream(req.message, req.session_id, req.location):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/parse")
async def parse_intent(req: ChatRequest):
    """
    Parse group order text into structured members + preferences.
    Returns: list of {member, cuisine, dish_keywords, budget_share}
    """
    result = await agent.parse_intent(req.message)
    return result
