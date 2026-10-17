"""TF-IDF retrieval over the curated knowledge_base/ — no network, no LLM."""

from regs_advisor.engine.retrieval import get_index, load_chunks


def test_loads_chunks_from_both_kb_files():
    chunks = load_chunks()
    sources = {c.source for c in chunks}
    assert sources == {"regulations_overview.md", "species_tackle.md"}
    assert len(chunks) > 5


def test_species_query_ranks_matching_section_first():
    idx = get_index()
    results = idx.top_k("best lure for smallmouth bass in summer", k=3)
    assert results
    assert "bass" in results[0][0].heading.lower()


def test_zone_query_surfaces_regulation_sections():
    idx = get_index()
    results = idx.top_k("what is the walleye catch limit", k=3)
    headings = [c.heading.lower() for c, _ in results]
    assert any("walleye" in h or "zone" in h or "limit" in h for h in headings)


def test_unrelated_query_returns_low_or_no_matches():
    idx = get_index()
    results = idx.top_k("xyzzy quantum blockchain nonsense", k=3)
    assert results == []


def test_live_bait_query_ranks_bait_rules_section_first():
    """Regression for the 'live bait allowed in quebec?' failure (see
    eval/results/diagnosis_live_bait.md): the province-wide ban must be the
    top-ranked chunk at the k=4 the router actually requests, not buried
    behind species-tackle chunks that merely mention bait as a technique."""
    idx = get_index()
    for query in [
        "live bait allowed in quebec?",
        "can I use minnows as bait?",
        "are shiners allowed as bait in Quebec?",
        "is bait fish legal?",
    ]:
        results = idx.top_k(query, k=4)
        assert results
        assert results[0][0].heading == "Bait rules", query
