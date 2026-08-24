"""
llm_client.py — regs_advisor.providers
------------------------------------------
Thin wrapper around the Groq API for the "Regs & Tips" chat endpoint.
Single-hop RAG: retrieved KB chunks + the user's question in one message,
one non-streaming call — no agentic loop, no tool use (see
docs/REGS_CHATBOT_PLAN.md "On LangChain": this is a single-hop retrieval
problem, not one that needs orchestration).
"""

import logging
import os

import groq

logger = logging.getLogger(__name__)

MODEL = os.getenv("REGS_CHAT_MODEL", "openai/gpt-oss-120b")
MAX_TOKENS = 1024

SYSTEM_PROMPT = (
    "You are a helpful assistant for Quebec sport fishing regulations and angling tips, "
    "part of the OMyFish app. Answer using ONLY the reference context provided in the user "
    "message — do not invent catch limits, season dates, or other numbers that aren't in the "
    "context. If the context doesn't cover the question, say so plainly and suggest checking "
    "quebec.ca or the app's structured Regs lookup instead of guessing. Keep answers concise. "
    "Always add a brief reminder to verify current regulations before fishing when the answer "
    "touches a legal limit, season, or consumption advisory."
)


class LLMError(RuntimeError):
    """Raised when the Groq API call fails or is refused."""


def _client() -> groq.Groq:
    return groq.Groq()


def ask(question: str, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks) if context_chunks else "(no matching reference material found)"
    user_message = f"Reference context:\n\n{context}\n\n---\n\nQuestion: {question}"

    # groq.GroqError (not just APIError) also covers client-construction
    # failures like a missing GROQ_API_KEY — catch it here so those surface
    # as a clean 503 instead of leaking an unhandled exception past the router.
    try:
        response = _client().chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
    except groq.GroqError as e:
        logger.warning("Groq API request failed: %s", e)
        raise LLMError(f"Groq API request failed: {e}") from e

    choice = response.choices[0]
    if choice.finish_reason == "content_filter":
        raise LLMError("The assistant declined to answer this question.")

    return (choice.message.content or "").strip()
