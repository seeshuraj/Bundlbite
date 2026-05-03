"""
Bundlbite LangGraph Agent
Multi-step pipeline: Parse -> Fetch -> Rank -> Respond
"""

import os
import json
from typing import AsyncGenerator
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict


SYSTEM_PROMPT = """
You are Bundlbite, an AI group food ordering assistant for India.
Your job:
1. Parse the group order message — extract each person's name, cuisine preference, and dish keywords.
2. Extract the total group budget in INR.
3. Extract the delivery location if mentioned.
4. Return a structured JSON with: members[], total_budget, location.

Always reply in JSON. If a field is missing, use null.
Handle Hinglish naturally (e.g. "Rahul ko biryani chahiye" = Rahul wants biryani).

Example output:
{
  "members": [
    {"name": "Rahul", "cuisine": "Biryani", "dish_keywords": ["chicken biryani"], "budget_share": null},
    {"name": "Sneha", "cuisine": "South Indian", "dish_keywords": ["dosa"], "budget_share": null}
  ],
  "total_budget": 1200,
  "location": "Indiranagar, Bangalore"
}
"""


class AgentState(TypedDict):
    message: str
    parsed: dict
    baskets: list
    response: str


class BundlbiteAgent:
    def __init__(self):
        # Prefer Anthropic, fall back to OpenAI
        if os.getenv("ANTHROPIC_API_KEY"):
            self.llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                temperature=0,
                max_tokens=2048,
            )
        else:
            self.llm = ChatOpenAI(
                model="gpt-4o",
                temperature=0,
            )

    async def parse_intent(self, message: str) -> dict:
        """
        Use LLM to extract structured order intent from natural language.
        """
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=message),
        ]
        response = await self.llm.ainvoke(messages)
        try:
            # Claude/GPT returns JSON in content
            content = response.content
            # Strip markdown code block if present
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content.strip())
        except Exception:
            return {"members": [], "total_budget": None, "location": None, "raw": response.content}

    async def stream(self, message: str, session_id: str, location: dict) -> AsyncGenerator:
        """
        Stream agent steps back to the client:
        1. Parsing intent
        2. Fetching from providers
        3. Optimising basket
        4. Returning result
        """
        yield {"step": "parsing", "message": "Parsing your group order..."}
        parsed = await self.parse_intent(message)
        yield {"step": "parsed", "data": parsed}

        if not parsed.get("members"):
            yield {"step": "error", "message": "Could not parse group order. Please describe each person's preference."}
            return

        yield {"step": "fetching", "message": f"Comparing Swiggy and Zomato for {len(parsed['members'])} people..."}

        # Budget optimisation is called from the orders router in real flow
        # Here we yield a summary response
        total = parsed.get("total_budget", 0)
        members = parsed.get("members", [])
        per_person = round(total / len(members), 2) if members else 0

        yield {
            "step": "complete",
            "message": (
                f"Found preferences for {len(members)} people. "
                f"Budget: \u20b9{total} (\u20b9{per_person}/person). "
                "Fetching best matches from Swiggy and Zomato now..."
            ),
            "data": parsed,
        }
