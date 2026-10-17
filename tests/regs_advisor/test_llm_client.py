"""REGS_FIX_GUARDRAIL system-prompt toggle — pure logic, no network."""

from regs_advisor.providers import llm_client


def test_guardrail_off_by_default(monkeypatch):
    monkeypatch.delenv("REGS_FIX_GUARDRAIL", raising=False)
    assert llm_client._system_prompt() == llm_client.SYSTEM_PROMPT


def test_guardrail_appends_addendum_when_flag_set(monkeypatch):
    monkeypatch.setenv("REGS_FIX_GUARDRAIL", "1")
    prompt = llm_client._system_prompt()
    assert prompt.startswith(llm_client.SYSTEM_PROMPT)
    assert "not confirmed in your sources" in prompt
