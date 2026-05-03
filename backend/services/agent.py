"""
Bundlbite LangGraph Agent
LLM: Qwen3-Coder-480B via NVIDIA NIM (OpenAI-compatible endpoint).
Streaming SSE responses to frontend.
"""

import os
import json
from typing import AsyncGenerator
from openai import AsyncOpenAI


def _get_nvidia_client() -> AsyncOpenAI:
    """
    Returns an async OpenAI client pointed at NVIDIA NIM.
    Uses NVIDIA_API_KEY from environment.
    """
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY not set. Get yours free at https://build.nvidia.com"
        )
    return AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )


MODEL = os.getenv("NVIDIA_MODEL", "qwen/qwen3-coder-480b-a35b-instruct")

SYSTEM_PROMPT = """
You are Bundlbite, an AI group food ordering assistant for India.
Your ONLY job is to parse group order messages and return structured JSON.

Rules:
- Reply with ONLY valid JSON. No markdown, no explanation, no code fences.
- Handle English, Hindi, and Hinglish naturally.
- If a field is unknown, use null.
- Extract: member names, cuisine/dish preferences, veg/non-veg flag, budget in INR, location.

Hinglish examples:
  "Rahul ko biryani chahiye"     → Rahul wants biryani
  "Priya veg hai"                → Priya is vegetarian
  "budget 1200 hai"              → total_budget: 1200
  "Koramangala mein order karo" → location: Koramangala

Output schema:
{
  "members": [
    {
      "name": "string",
      "cuisine": "string",
      "dish_keywords": ["string"],
      "is_veg": true | false | null,
      "budget_share": number | null
    }
  ],
  "total_budget": number | null,
  "location": "string | null"
}
"""


class BundlbiteAgent:
    def __init__(self):
        self.client = _get_nvidia_client()

    async def parse_intent(self, message: str) -> dict:
        """
        Use Qwen3-480B to extract structured order intent from
        natural language / Hinglish group order text.
        """
        try:
            response = await self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                temperature=0.2,   # Low temp for deterministic JSON
                top_p=0.8,
                max_tokens=1024,
                stream=False,
            )
            content = response.choices[0].message.content or ""

            # Strip markdown code fences if model adds them
            if "```" in content:
                for part in content.split("```"):
                    part = part.strip().lstrip("json").strip()
                    try:
                        return json.loads(part)
                    except Exception:
                        continue

            return json.loads(content.strip())

        except json.JSONDecodeError:
            return {
                "members": [],
                "total_budget": None,
                "location": None,
                "error": "JSON parse failed",
                "raw": content,
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
        Stream agent steps as SSE events to the frontend.
        Uses Qwen3-480B streaming for the parse step.
        """
        yield {"step": "parsing", "message": "Parsing your group order with Qwen3-480B..."}

        # ---- Streaming parse (shows token-by-token to user) ----
        full_content = ""
        try:
            stream = await self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
                temperature=0.2,
                top_p=0.8,
                max_tokens=1024,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full_content += delta
                    yield {"step": "token", "delta": delta}  # stream tokens to UI
        except Exception as e:
            yield {"step": "error", "message": f"LLM error: {e}"}
            return

        # ---- Parse the accumulated JSON ----
        parsed = {}
        try:
            content = full_content.strip()
            if "```" in content:
                for part in content.split("```"):
                    part = part.strip().lstrip("json").strip()
                    try:
                        parsed = json.loads(part)
                        break
                    except Exception:
                        continue
            else:
                parsed = json.loads(content)
        except Exception:
            parsed = {"members": [], "total_budget": None, "location": None, "raw": full_content}

        yield {"step": "parsed", "data": parsed}

        members = parsed.get("members", [])
        total = parsed.get("total_budget") or 0

        if not members:
            yield {
                "step": "error",
                "message": (
                    "Could not parse the group order. "
                    "Try: 'Rahul wants biryani, Sneha wants dosa, budget \u20b91200, Koramangala'"
                ),
            }
            return

        per_person = round(total / len(members), 2) if members and total else 0
        yield {"step": "fetching", "message": f"Comparing Swiggy & Zomato for {len(members)} people..."}

        yield {
            "step": "complete",
            "message": (
                f"Parsed {len(members)} members. "
                f"Budget: \u20b9{total} (\u20b9{per_person}/person). "
                "Fetching best baskets..."
            ),
            "data": parsed,
        }
