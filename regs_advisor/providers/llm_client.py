"""
llm_client.py — regs_advisor.providers
------------------------------------------
Thin wrapper around the Claude API for the "Regs & Tips" chat endpoint.
Single-hop RAG: retrieved KB chunks + the user's question in one message,
one non-streaming call — no agentic loop, no tool use (see
docs/REGS_CHATBOT_PLAN.md "On LangChain": this is a single-hop retrieval
problem, not one that needs orchestration).
"""

import os

import anthropic

MODEL = os.getenv("REGS_CHAT_MODEL", "claude-opus-5")
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
    """Raised when the Claude API call fails or is refused."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def ask(question: str, context_chunks: list[str]) -> str:
    context = "\n\n---\n\n".join(context_chunks) if context_chunks else "(no matching reference material found)"
    user_message = f"Reference context:\n\n{context}\n\n---\n\nQuestion: {question}"

    try:
        response = _client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as e:
        raise LLMError(f"Claude API request failed: {e}") from e

    if response.stop_reason == "refusal":
        raise LLMError("The assistant declined to answer this question.")

    return next((b.text for b in response.content if b.type == "text"), "").strip()
