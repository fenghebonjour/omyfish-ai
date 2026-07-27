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
