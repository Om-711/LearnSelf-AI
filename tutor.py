"""Gemini-powered learning assistant."""

from __future__ import annotations

import os

from google import genai
from google.genai import types

SYSTEM_INSTRUCTION = """You are LearnSelf, a warm and concise learning assistant.
Explain concepts at the learner's level. Include a short explanation, one practical
example, and one check-for-understanding question. Be transparent if unsure."""


def answer_stream(question: str, progress: str, history: str, memories: str):
    """Yield Gemini text chunks so Streamlit can render an answer as it arrives."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to your .env file.")

    client = genai.Client(api_key=api_key)
    prompt = f"""Learner progress: {progress}

What this learner has asked before:
{history or "No earlier messages."}

Remembered learner details for this chat:
{memories or "No saved details yet."}

Learner question: {question}"""
    stream = client.models.generate_content_stream(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.4),
    )
    received_text = False
    for chunk in stream:
        if chunk.text:
            received_text = True
            yield chunk.text
    if not received_text:
        raise RuntimeError("Gemini returned no text response.")
