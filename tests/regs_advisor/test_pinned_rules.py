"""REGS_FIX_PINNED core-rules block — pure logic, no network, no LLM."""

from regs_advisor.engine.pinned_rules import load_core_rules_block


def test_core_rules_block_includes_licensing_and_bait_rules():
    block = load_core_rules_block()
    assert "12" in block  # licensing age
    assert "live bait fish" in block.lower()
    assert "2017" in block
    assert "regulations_overview.md" in block  # source citation present
