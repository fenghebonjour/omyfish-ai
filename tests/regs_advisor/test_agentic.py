"""REGS_FIX_GUARDRAIL leaked-citation stripping — pure logic, no network."""

from regs_advisor.engine.agentic import _strip_leaked_citations


def test_leaves_answer_unchanged_when_flag_off(monkeypatch):
    monkeypatch.delenv("REGS_FIX_GUARDRAIL", raising=False)
    answer = "Live bait fish are banned province-wide.【12†source】"
    assert _strip_leaked_citations(answer) == answer


def test_strips_leaked_citation_markers_when_flag_on(monkeypatch):
    monkeypatch.setenv("REGS_FIX_GUARDRAIL", "1")
    answer = "Live bait fish are banned province-wide.【12†source】 Check quebec.ca."
    stripped = _strip_leaked_citations(answer)
    assert "【" not in stripped
    assert "banned province-wide" in stripped
