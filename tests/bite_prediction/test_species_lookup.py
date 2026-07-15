"""Resolver from confirmed fish-ID names to bite-score profile keys."""

from bite_prediction.engine import resolve_species_key


def test_resolves_profile_key_common_and_scientific_names():
    assert resolve_species_key("largemouth_bass") == "largemouth_bass"
    assert resolve_species_key("Largemouth Bass") == "largemouth_bass"
    assert resolve_species_key("Micropterus salmoides") == "largemouth_bass"
    assert resolve_species_key("Sander vitreus") == "walleye"


def test_unknown_species_returns_none():
    assert resolve_species_key("Thunnus thynnus") is None
