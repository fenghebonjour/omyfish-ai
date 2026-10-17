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

# REGS_FIX_GUARDRAIL: a species/tackle description that merely mentions an item (e.g. a
# "live-bait rig") is not a rule permitting or banning it. Off by default -- see
# eval/results/diagnosis_live_bait.md for the failure this addresses.
GUARDRAIL_ADDENDUM = (
    " A passage that merely describes a technique or mentions an item (e.g. a species "
    "entry saying anglers use a \"live-bait rig\") is NOT a rule stating that item is "
    "legal or illegal. For a yes/no legality question, only answer yes or no if the "
    "context contains an explicit rule statement covering it; otherwise say the answer "
    "is not confirmed in your sources and point to quebec.ca."
)


def _system_prompt() -> str:
    if os.getenv("REGS_FIX_GUARDRAIL"):
        return SYSTEM_PROMPT + GUARDRAIL_ADDENDUM
    return SYSTEM_PROMPT


class LLMError(RuntimeError):
    """Raised when the Groq API call fails or is refused."""


def _client() -> groq.Groq:
    # The only outbound call in this service with no explicit timeout/retry — a slow Groq
    # response could hang the request indefinitely otherwise. max_retries uses the SDK's
    # own exponential backoff, matching the intent (if not the exact mechanism) of
    # weather_client.py's retry loop elsewhere in this repo
    # (BACKLOG.md item G, WEAKNESS_AUDIT.md §2.1).
    return groq.Groq(timeout=15.0, max_retries=2)


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
                {"role": "system", "content": _system_prompt()},
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
