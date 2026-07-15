"""
species_profiles.py
--------------------
Per-species tuning for the OMyFish Bite Score engine.

Every profile is just data: weights (must sum to 1.0 across the six
factors) plus the parameters of that species' temperature comfort band.
This is the whole point of the "transparent model" pitch — a PM, a
biologist, or a power user can open this file and see exactly why the
smallmouth bass score differs from the catfish score. No retraining,
no opaque coefficients.

Weights were seeded from classic angling literature (pressure trend and
temperature dominate for sight-feeding gamefish; water movement and low
light dominate for catfish/walleye) and are DESIGNED to be overwritten
by the calibration layer in `calibration.py` once catch-log data exists
for a region/species pair.
"""

from dataclasses import dataclass, field


@dataclass
class TemperatureBand:
    """Trapezoidal comfort band, in Celsius."""
    min_ok: float     # feeding starts
    opt_low: float    # start of optimal plateau
    opt_high: float   # end of optimal plateau
    max_ok: float      # feeding stops


@dataclass
class SpeciesProfile:
    name: str
    temp_band: TemperatureBand
    weights: dict          # keys: pressure, temperature, wind, water, solunar, sky
    dawn_dusk_boost: float = 1.15   # multiplier applied in crepuscular windows
    low_light_lover: bool = False   # e.g. catfish/walleye — extra boost on overcast/low light

    def __post_init__(self):
        total = sum(self.weights.values())
        if not (0.98 <= total <= 1.02):
            raise ValueError(f"{self.name}: weights must sum to ~1.0, got {total}")


PROFILES: dict[str, SpeciesProfile] = {
    "smallmouth_bass": SpeciesProfile(
        name="Smallmouth Bass",
        temp_band=TemperatureBand(min_ok=10, opt_low=18, opt_high=23, max_ok=27),
        weights={"pressure": 0.28, "temperature": 0.22, "wind": 0.14,
                 "water": 0.14, "solunar": 0.12, "sky": 0.10},
    ),
    "largemouth_bass": SpeciesProfile(
        name="Largemouth Bass",
        temp_band=TemperatureBand(min_ok=13, opt_low=21, opt_high=27, max_ok=32),
        weights={"pressure": 0.24, "temperature": 0.20, "wind": 0.12,
                 "water": 0.16, "solunar": 0.14, "sky": 0.14},
    ),
    "walleye": SpeciesProfile(
        name="Walleye",
        temp_band=TemperatureBand(min_ok=7, opt_low=15, opt_high=20, max_ok=24),
        weights={"pressure": 0.20, "temperature": 0.14, "wind": 0.10,
                 "water": 0.18, "solunar": 0.16, "sky": 0.22},
        low_light_lover=True,
        dawn_dusk_boost=1.30,
    ),
    "channel_catfish": SpeciesProfile(
        name="Channel Catfish",
        temp_band=TemperatureBand(min_ok=15, opt_low=24, opt_high=29, max_ok=33),
        weights={"pressure": 0.14, "temperature": 0.16, "wind": 0.08,
                 "water": 0.32, "solunar": 0.14, "sky": 0.16},
        low_light_lover=True,
        dawn_dusk_boost=1.20,
    ),
    "rainbow_trout": SpeciesProfile(
        name="Rainbow Trout",
        temp_band=TemperatureBand(min_ok=4, opt_low=10, opt_high=16, max_ok=19),
        weights={"pressure": 0.26, "temperature": 0.24, "wind": 0.12,
                 "water": 0.16, "solunar": 0.10, "sky": 0.12},
    ),
    "general": SpeciesProfile(
        name="General / Unknown Species",
        temp_band=TemperatureBand(min_ok=8, opt_low=16, opt_high=24, max_ok=29),
        weights={"pressure": 0.24, "temperature": 0.18, "wind": 0.12,
                 "water": 0.18, "solunar": 0.14, "sky": 0.14},
    ),
}


def get_profile(species_key: str) -> SpeciesProfile:
    return PROFILES.get(species_key, PROFILES["general"])


# Maps names a confirmed fish ID can produce (scientific names, and the
# identification service's normalized common-name keys) onto profile keys.
# Normalization matches main.py's: lower, spaces/hyphens -> underscores.
_SPECIES_ALIASES: dict[str, str] = {
    "micropterus_dolomieu": "smallmouth_bass",
    "micropterus_salmoides": "largemouth_bass",
    "sander_vitreus": "walleye",
    "stizostedion_vitreum": "walleye",
    "ictalurus_punctatus": "channel_catfish",
    "oncorhynchus_mykiss": "rainbow_trout",
}


def resolve_species_key(name: str) -> str | None:
    """Resolve a fish-ID result (common or scientific name, any casing)
    to a PROFILES key, or None if no tuned profile exists for it."""
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    if key in PROFILES:
        return key
    return _SPECIES_ALIASES.get(key)
