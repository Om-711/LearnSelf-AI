"""A minimal LangGraph workflow whose remember node writes learner facts to PostgreSQL."""

from __future__ import annotations

import json
import os
from typing import TypedDict

from google import genai
from google.genai import types
from langgraph.graph import END, START, StateGraph

from database import Database


class MemoryState(TypedDict):
    chat_id: str
    user_message: str
    memories: list[dict[str, str]]


EXTRACTION_INSTRUCTION = """Extract only stable learner information explicitly stated by the user,
such as skill_level, learning_goal, preferred_explanation_style, or difficult_topic.
Return a JSON array of objects with exactly `key` and `value` fields. Return [] for
questions containing no useful lasting learner detail. Never infer personal facts."""


def build_remember_graph(db: Database):
    def remember_node(state: MemoryState) -> dict:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"memories": []}
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=state["user_message"],
            config=types.GenerateContentConfig(
                system_instruction=EXTRACTION_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        try:
            memories = json.loads(response.text or "[]")
        except json.JSONDecodeError:
            memories = []
        valid_memories = [
            item for item in memories
            if isinstance(item, dict) and isinstance(item.get("key"), str) and isinstance(item.get("value"), str)
        ]
        for item in valid_memories:
            db.save_memory(state["chat_id"], item["key"][:80], item["value"][:500])
        return {"memories": valid_memories}

    builder = StateGraph(MemoryState)
    builder.add_node("remember", remember_node)
    builder.add_edge(START, "remember")
    builder.add_edge("remember", END)
    return builder.compile()
