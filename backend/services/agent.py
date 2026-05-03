"""
Bundlbite LangGraph Agent
LLM: Qwen3 via Ollama (local) with Groq cloud fallback.
No Anthropic or OpenAI dependency.
"""

import os
import json
from typing import AsyncGenerator
from langchain_core.messages import HumanMessage, SystemMessage


def _get_llm():
    """
    LLM priority:
    1. Ollama local (Qwen3) — zero cost, best for dev
    2. Groq API (Qwen3) — free tier, 800 tok/s, best for prod
    3. OpenAI GPT-4o — fallback if both unavailable
    """
    # Option 1: Ollama local
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        from langchain_ollama import ChatOllama
        model_name = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        llm = ChatOllama(
            model=model_name,
            base_url=ollama_base,
            temperature=0,
            format="json",  # Force JSON output mode
        )
        # Quick connectivity check
        import httpx
        resp = httpx.get(f"{ollama_base}/api/tags", timeout=2)
        if resp.status_code == 200:
            print(f"[BundlbiteAgent] Using Ollama Qwen3 @ {ollama_base}")
            return llm
    except Exception as e:
        print(f"[BundlbiteAgent] Ollama unavailable: {e}")

    # Option 2: Groq (hosts Qwen3, free tier)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from langchain_groq import ChatGroq
            model_name = os.getenv("GROQ_MODEL", "qwen-qwq-32b")  # Qwen3 on Groq
            llm = ChatGroq(
                model=model_name,
                temperature=0,
                api_key=groq_key,
            )
            print(f"[BundlbiteAgent] Using Groq Qwen3: {model_name}")
            return llm
        except Exception as e:
            print(f"[BundlbiteAgent] Groq unavailable: {e}")

    # Option 3: OpenAI fallback
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        from langchain_openai import ChatOpenAI
        print("[BundlbiteAgent] Falling back to OpenAI GPT-4o")
        return ChatOpenAI(model="gpt-4o", temperature=0, api_key=openai_key)

    raise RuntimeError(
        "No LLM configured. Set OLLAMA_BASE_URL, GROQ_API_KEY, or OPENAI_API_KEY."
    )


SYSTEM_PROMPT = """
You are Bundlbite, an AI group food ordering assistant for India.
Your job:
1. Parse the group order message — extract each person's name, cuisine preference, and dish keywords.
2. Extract the total group budget in INR.
3. Extract the delivery location if mentioned.
4. Return a structured JSON with: members[], total_budget, location.

Always reply with ONLY valid JSON. No markdown, no explanation — just the JSON object.
Handle Hinglish naturally:
  - "Rahul ko biryani chahiye" → Rahul wants biryani
  - "Priya veg hai" → Priya is vegetarian
  - "budget 1200 hai" → total_budget: 1200

Example output:
{
  "members": [
    {"name": "Rahul", "cuisine": "Biryani", "dish_keywords": ["chicken biryani"], "budget_share": null, "is_veg": false},
    {"name": "Priya", "cuisine": "South Indian", "dish_keywords": ["dosa", "idli"], "budget_share": null, "is_veg": true}
  ],
  "total_budget": 1200,
  "location": "Indiranagar, Bangalore"
}
"""


class BundlbiteAgent:
    def __init__(self):
        self.llm = _get_llm()

    async def parse_intent(self, message: str) -> dict:
        """
        Use Qwen3 to extract structured order intent from natural language / Hinglish.
        """
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=message),
        ]
        try:
            response = await self.llm.ainvoke(messages)
            content = response.content

            # Strip markdown code fences if model adds them
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:]
                    try:
                        return json.loads(part.strip())
                    except Exception:
                        continue

            return json.loads(content.strip())
        except json.JSONDecodeError:
            # Fallback: return raw content for debugging
            return {
                "members": [],
                "total_budget": None,
                "location": None,
                "raw": response.content,
                "error": "JSON parse failed",
            }
        except Exception as e:
            return {
                "members": [],
                "total_budget": None,
                "location": None,
                "error": str(e),
            }

    async def stream(self, message: str, session_id: str, location: dict) -> AsyncGenerator:
        """
        Stream agent steps back to the client as SSE events.
        Steps: parsing → parsed → fetching → complete
        """
        yield {"step": "parsing", "message": "Parsing your group order with Qwen3..."}

        parsed = await self.parse_intent(message)
        yield {"step": "parsed", "data": parsed}

        if not parsed.get("members"):
            yield {
                "step": "error",
                "message": (
                    "Could not parse the group order. "
                    "Try: 'Rahul wants biryani, Sneha wants dosa, budget 1200, Koramangala'"
                ),
            }
            return

        members = parsed.get("members", [])
        total = parsed.get("total_budget") or 0
        per_person = round(total / len(members), 2) if members and total else 0

        yield {"step": "fetching", "message": f"Comparing Swiggy & Zomato for {len(members)} people..."}

        yield {
            "step": "complete",
            "message": (
                f"Parsed {len(members)} members. "
                f"Budget: \u20b9{total} (\u20b9{per_person}/person). "
                "Fetching best baskets from Swiggy and Zomato..."
            ),
            "data": parsed,
        }
