"""
agentic.py — regs_advisor.engine
-----------------------------------
Optional agentic retrieval mode for /regs/ask, gated by REGS_MODE=agentic in
router.py (default is unset, which keeps the single-hop path there completely
untouched). Uses Groq tool calling with one tool, search_regs, which wraps
the existing TF-IDF retriever (engine/retrieval.py — not modified) so the
model can issue multiple, reformulated searches for compound or casually-
worded questions instead of a single fixed-k retrieval pass.

Empirically verified against the configured model (REGS_CHAT_MODEL, default
openai/gpt-oss-120b via llm_client.MODEL):
  - It supports tool calling (tested directly against the Groq API before
    writing this module).
  - Passing tool_choice="none" (or omitting `tools` entirely) on a later turn
    in the same conversation makes the API return 400 "Tool choice is none,
    but model called a tool" — this model's own internal tool-use state
    doesn't respect that. So the only reliable way found to force a final,
    non-tool answer is to keep `tools`/tool_choice="auto" on every turn and
    instead tell the model via a plain user message that its search budget
    is spent and it must answer now from what it already has.
  - It has a hidden reasoning channel (response.usage.reasoning_tokens) that
    counts against max_tokens — a low max_tokens can return empty content
    with finish_reason="length" before any visible answer is produced.
  - Left unconstrained, it will retry near-identical searches repeatedly
    rather than give up, so the call cap below is load-bearing, not just a
    cost guard.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field

import groq

from regs_advisor.engine.pinned_rules import load_core_rules_block
from regs_advisor.engine.retrieval import get_index
from regs_advisor.providers.llm_client import MODEL, LLMError

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 3
TOP_K_PER_CALL = 3
MAX_TOKENS = 1536  # generous: this model's hidden reasoning channel eats into max_tokens

SYSTEM_PROMPT = (
    "You are a helpful assistant for Quebec sport fishing regulations and angling tips, "
    "part of the OMyFish app. You have one tool, search_regs, over a small knowledge base "
    "of regulation and tackle notes. Rules:\n"
    "- If the question asks about more than one fact, species, or zone, split it into "
    "separate search_regs calls, one per fact, instead of one combined query.\n"
    "- The knowledge base is written in the regulations' own formal terms, not casual "
    "angler slang. Rewrite casual wording into those terms before searching -- for example "
    "'minnows'/'shiners' -> 'live bait fish', 'keepers' -> 'catch limit' / 'possession limit', "
    "'tags' or 'permit' -> 'licence'.\n"
    "- If a search's results don't contain the fact you need, rewrite the query and search "
    "again before giving up on that fact.\n"
    "- You may call search_regs at most 3 times in total across the whole conversation. "
    "Once you are told your search budget is spent, you must answer immediately using only "
    "what you already retrieved -- do not attempt another search.\n"
    "- Answer using ONLY information returned by search_regs -- never invent catch limits, "
    "season dates, or other numbers that aren't in the search results. If your searches "
    "didn't turn up the answer, say so plainly and suggest checking quebec.ca or the app's "
    "structured Regs lookup instead of guessing.\n"
    "- Keep answers concise. Always add a brief reminder to verify current regulations "
    "before fishing when the answer touches a legal limit, season, or consumption advisory."
)

# REGS_FIX_GUARDRAIL -- see llm_client.py's GUARDRAIL_ADDENDUM for the basic-mode
# equivalent; same failure mode, worded for the tool-calling system prompt here.
GUARDRAIL_ADDENDUM = (
    " A passage that merely describes a technique or mentions an item (e.g. a species "
    "entry saying anglers use a \"live-bait rig\") is NOT a rule stating that item is "
    "legal or illegal. For a yes/no legality question, only answer yes or no if a "
    "search_regs result contains an explicit rule statement covering it; otherwise say "
    "the answer is not confirmed in your sources and point to quebec.ca."
)

_LEAKED_CITATION_RE = re.compile(r"【[^】]*】")

BUDGET_SPENT_MESSAGE = (
    "You have used all 3 of your allowed searches. Give your final answer now, using only "
    "the search results already returned above. Do not call search_regs again."
)

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_regs",
        "description": (
            "Search the Quebec fishing regulations / tackle knowledge base. Returns up to "
            "3 matching passages with their chunk ids. Rewrite casual angler wording into "
            "the regulations' own formal terms before calling."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query, in the KB's formal terminology."},
                "species": {
                    "type": ["string", "null"],
                    "description": "Species name if the question names one, else null.",
                },
                "zone": {
                    "type": ["string", "null"],
                    "description": "Zone name or number if the question names one, else null.",
                },
            },
            "required": ["query", "species", "zone"],
        },
    },
}


def search_regs(query: str, species: str | None, zone: str | None) -> list[dict]:
    """The one tool exposed to the model. Wraps the existing TF-IDF index
    (engine/retrieval.py, unchanged) -- folds species/zone into the query
    text since the retriever has no separate structured fields."""
    full_query = " ".join(p for p in [query, species, zone] if p)
    hits = get_index().top_k(full_query, k=TOP_K_PER_CALL)
    return [
        {"id": f"{c.source}#{c.heading}", "file": c.source, "heading": c.heading, "text": c.text, "score": round(score, 4)}
        for c, score in hits
    ]


@dataclass
class AgenticResult:
    answer: str
    sources: list[str]
    queries: list[dict] = field(default_factory=list)
    retrieved_chunks: list[dict] = field(default_factory=list)
    tool_call_count: int = 0
    hit_budget_cap: bool = False


def _client() -> groq.Groq:
    return groq.Groq(timeout=20.0, max_retries=2)


def _call(client: groq.Groq, messages: list[dict]):
    try:
        return client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=messages,
            tools=[SEARCH_TOOL],
            tool_choice="auto",
        )
    except groq.GroqError as e:
        logger.warning("Groq API request failed (agentic): %s", e)
        raise LLMError(f"Groq API request failed: {e}") from e


def _strip_leaked_citations(answer: str) -> str:
    if os.getenv("REGS_FIX_GUARDRAIL"):
        return _LEAKED_CITATION_RE.sub("", answer).strip()
    return answer


def ask_agentic(question: str) -> AgenticResult:
    system_prompt = SYSTEM_PROMPT
    if os.getenv("REGS_FIX_GUARDRAIL"):
        system_prompt += GUARDRAIL_ADDENDUM
    if os.getenv("REGS_FIX_PINNED"):
        system_prompt += "\n\n" + load_core_rules_block()

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    queries: list[dict] = []
    seen_chunks: dict[str, dict] = {}
    tool_call_count = 0
    budget_message_sent = False

    while True:
        response = _call(client=_client(), messages=messages)
        choice = response.choices[0]
        msg = choice.message

        if not msg.tool_calls:
            answer = (msg.content or "").strip()
            if not answer:
                answer = "Unable to produce a final answer within the tool-call budget."
            answer = _strip_leaked_citations(answer)
            return AgenticResult(
                answer=answer,
                sources=[c["heading"] for c in seen_chunks.values()],
                queries=queries,
                retrieved_chunks=list(seen_chunks.values()),
                tool_call_count=tool_call_count,
                hit_budget_cap=budget_message_sent,
            )

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })

        for tc in msg.tool_calls:
            if tool_call_count >= MAX_TOOL_CALLS:
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": "Search budget already spent -- this call was not executed.",
                })
                continue
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            query = args.get("query") or ""
            species = args.get("species")
            zone = args.get("zone")
            results = search_regs(query, species, zone)
            tool_call_count += 1
            queries.append({"query": query, "species": species, "zone": zone, "result_ids": [r["id"] for r in results]})
            for r in results:
                seen_chunks.setdefault(r["id"], r)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps([{"id": r["id"], "heading": r["heading"], "text": r["text"]} for r in results]),
            })

        if tool_call_count >= MAX_TOOL_CALLS and not budget_message_sent:
            messages.append({"role": "user", "content": BUDGET_SPENT_MESSAGE})
            budget_message_sent = True
        elif budget_message_sent:
            # The forced "answer now" turn still called a tool (not executed above) instead
            # of answering in text. Don't loop forever -- surface whatever was retrieved.
            answer = (msg.content or "").strip() or (
                "Search budget spent and no final answer was produced -- "
                "here is what the searches found, unconfirmed: "
                + "; ".join(f"{c['heading']}" for c in seen_chunks.values())
            )
            answer = _strip_leaked_citations(answer)
            return AgenticResult(
                answer=answer,
                sources=[c["heading"] for c in seen_chunks.values()],
                queries=queries,
                retrieved_chunks=list(seen_chunks.values()),
                tool_call_count=tool_call_count,
                hit_budget_cap=True,
            )
