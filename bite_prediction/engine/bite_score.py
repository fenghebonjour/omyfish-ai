"""
bite_score.py
--------------
Core Bite Score engine for OMyFish.

Design goals (this is the actual moat, so keep it honest):
  1. Every sub-score is 0-100 and independently explainable.
  2. The aggregate score always ships with a per-factor breakdown —
     never just a number.
  3. Nothing here is a black box: every curve is a plain function with
     a docstring justifying its shape. A reviewer, a biologist, or a
     future teammate can read this file top to bottom and understand
     the whole model in ten minutes.
  4. This module is pure math over a typed input — no I/O, no HTTP.
     The FastAPI layer (see `api.py`) is responsible for fetching
     weather/tide data and calling into this.

Nothing here requires ML to run day one. `calibration.py` describes
how a learned layer plugs in *on top of* this once catch-log data
exists, without replacing the transparent baseline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

from .species_profiles import SpeciesProfile, get_profile


# --------------------------------------------------------------------------- #
# Input contract — one hourly weather/tide observation (or forecast point)
# --------------------------------------------------------------------------- #

@dataclass
class HourlyConditions:
    timestamp: datetime
    air_temp_c: float
    feels_like_c: float
    pressure_hpa: float
    pressure_delta_3h: float     # hPa change over previous 3 hours (signed)
    pressure_delta_24h: float    # hPa change over previous 24 hours (signed)
    wind_speed_kmh: float
    cloud_cover_pct: float       # 0-100
    precip_mm: float             # last 1h
    is_storm: bool               # lightning/severe flag from provider
    moon_phase: float            # 0.0 = new, 0.5 = full, 1.0 = new (cycle fraction)
    minutes_from_moon_major: float   # minutes to nearest moon-overhead/underfoot event
    minutes_from_moon_minor: float   # minutes to nearest moonrise/moonset event
    is_heavy_precip: bool = False    # heavy rain/snow codes without a storm flag
    # Chance of any rain (0-100, provider forecast). Display-only passthrough:
    # scoring uses intensity (precip_mm) — fish don't mind rain, anglers do.
    precip_probability_pct: Optional[float] = None
    # Exactly one of the two water blocks should be populated by the caller
    tide_rate_m_per_hr: Optional[float] = None   # signed; None if non-tidal water
    tide_pct_to_extreme: Optional[float] = None  # 0=at high/low, 1=at slack midpoint
    lake_level_trend_cm_per_day: Optional[float] = None  # signed; None if tidal water
    sunrise: Optional[time] = None
    sunset: Optional[time] = None


@dataclass
class FactorBreakdown:
    pressure: float
    temperature: float
    wind: float
    water: float
    solunar: float
    sky: float

    def as_dict(self) -> dict:
        return {
            "pressure": round(self.pressure, 1),
            "temperature": round(self.temperature, 1),
            "wind": round(self.wind, 1),
            "water": round(self.water, 1),
            "solunar": round(self.solunar, 1),
            "sky": round(self.sky, 1),
        }


@dataclass
class BiteScoreResult:
    timestamp: datetime
    score: float                  # 0-100 final, headline number
    breakdown: FactorBreakdown     # raw 0-100 sub-scores, before weighting
    weighted_contribution: dict    # each factor's actual point contribution to `score`
    time_of_day_multiplier: float
    safety_flag: Optional[str] = None
    precip_probability_pct: Optional[float] = None  # display-only, not scored


# --------------------------------------------------------------------------- #
# Individual factor curves
# --------------------------------------------------------------------------- #

def score_pressure(hpa: float, delta_3h: float, delta_24h: float) -> float:
    """
    Base level: gaussian centered on 1017 hPa (a commonly cited 'settled
    weather' baseline) — extreme highs and lows both suppress activity.

    Trend multiplier: slow falling pressure ahead of a front is the
    single most-cited positive signal in angling literature; sharp
    post-frontal rises are the most-cited negative one.
    """
    base = 100 * math.exp(-((hpa - 1017.0) ** 2) / (2 * 15.0 ** 2))

    if -3.0 <= delta_3h < -0.5:
        trend = 1.30       # slow, steady fall — classic pre-frontal window
    elif delta_3h < -3.0:
        trend = 1.05        # sharp fall — fish often feed heavily just before it hits
    elif abs(delta_3h) <= 0.5:
        trend = 1.00        # stable
    elif 0.5 < delta_3h <= 2.0:
        trend = 0.80        # slow rise — post-frontal settling
    else:
        trend = 0.55         # sharp rise — classic post-frontal lull

    # 24h trend softens/reinforces the 3h read rather than overriding it
    if delta_24h < -2.0 and delta_3h < 0:
        trend *= 1.08
    elif delta_24h > 4.0:
        trend *= 0.92

    return max(0.0, min(100.0, base * trend))


def score_temperature(air_temp_c: float, band: "TemperatureBand") -> float:
    """Trapezoidal membership: 0 outside [min_ok, max_ok], 100 on the
    optimal plateau, linear ramps between."""
    t = air_temp_c
    if t <= band.min_ok or t >= band.max_ok:
        return 0.0
    if band.opt_low <= t <= band.opt_high:
        return 100.0
    if t < band.opt_low:
        return 100.0 * (t - band.min_ok) / (band.opt_low - band.min_ok)
    return 100.0 * (band.max_ok - t) / (band.max_ok - band.opt_high)


def score_wind(speed_kmh: float) -> float:
    """
    Peaked, asymmetric curve. Light-to-moderate wind (~6-18 km/h) breaks
    up surface glare, oxygenates water, and drives baitfish — the
    'walleye chop' effect. Dead calm and gale-force wind both score low,
    but the fall-off is gentler on the calm side than the rough side.
    """
    peak = 12.0
    if speed_kmh <= peak:
        return 100.0 * math.exp(-((speed_kmh - peak) ** 2) / (2 * 9.0 ** 2))
    return 100.0 * math.exp(-((speed_kmh - peak) ** 2) / (2 * 6.0 ** 2))


def score_water(cond: HourlyConditions) -> float:
    """
    Tidal water: scored on how much the tide is actively moving (rate
    of change), since slack tide is the classic dead period.
    Non-tidal water: scored on level trend — a gently rising level opens
    new feeding structure along the shoreline; a rapidly falling level
    strands fish and shuts down the bite.
    """
    if cond.tide_rate_m_per_hr is not None:
        rate = abs(cond.tide_rate_m_per_hr)
        return max(0.0, min(100.0, 100.0 * min(rate / 0.35, 1.0)))

    if cond.lake_level_trend_cm_per_day is not None:
        trend = cond.lake_level_trend_cm_per_day
        if 0 <= trend <= 5:
            return 100.0 - (trend / 5.0) * 15.0   # slightly rising: great, near-perfect
        if trend > 5:
            return max(30.0, 85.0 - (trend - 5) * 4)  # flooding: diminishing returns
        return max(0.0, 70.0 + trend * 8)          # falling: drops fast (trend is negative)

    return 60.0  # no data — neutral-leaning default, not a false positive


def score_solunar(cond: HourlyConditions) -> float:
    """
    Boosts near a major period (moon overhead/underfoot, ~2h window) or
    minor period (moonrise/moonset, ~1h window), layered on a mild
    full/new-moon phase bonus. This is the most "folklore" factor in the
    model, so it is intentionally capped at a moderate weight in every
    species profile above.
    """
    major = max(0.0, 100.0 - (abs(cond.minutes_from_moon_major) / 120.0) * 100.0)
    minor = max(0.0, 80.0 - (abs(cond.minutes_from_moon_minor) / 60.0) * 80.0)
    window_score = max(major, minor)

    phase_distance_from_full_or_new = min(abs(cond.moon_phase - 0.0),
                                           abs(cond.moon_phase - 0.5),
                                           abs(cond.moon_phase - 1.0))
    phase_bonus = max(0.0, 15.0 * (1 - phase_distance_from_full_or_new / 0.25))

    return max(0.0, min(100.0, window_score * 0.85 + phase_bonus))


def score_sky(cond: HourlyConditions) -> float:
    """
    Stable overcast (40-85% cloud) extends low-light feeding conditions
    through the day. Clear bluebird sky suppresses shallow activity.
    A light, steady rain (<=2mm/h) ahead of or during a front often
    triggers a feeding spike; heavy rain or any storm flag overrides
    everything else with a safety-first low score.
    """
    if cond.is_storm:
        return 5.0

    cloud = cond.cloud_cover_pct
    if 40 <= cloud <= 85:
        cloud_score = 90.0 + (min(cloud, 70) - 40) / 30 * 10 if cloud <= 70 else 100 - (cloud - 70) * 0.3
    elif cloud < 40:
        cloud_score = 60.0 * (cloud / 40.0)
    else:
        cloud_score = max(50.0, 100 - (cloud - 85) * 1.5)

    if 0 < cond.precip_mm <= 2.0:
        precip_bonus = 12.0
    elif cond.precip_mm > 2.0:
        precip_bonus = -20.0
    else:
        precip_bonus = 0.0

    return max(0.0, min(100.0, cloud_score + precip_bonus))


def time_of_day_multiplier(ts: datetime, sunrise: Optional[time],
                            sunset: Optional[time], profile: SpeciesProfile) -> float:
    """Crepuscular boost: most species feed harder within ~45 min of
    sunrise/sunset regardless of the weather-driven score above."""
    if not sunrise or not sunset:
        return 1.0

    t = ts.time()

    def _mins(a: time, b: time) -> float:
        return abs((a.hour * 60 + a.minute) - (b.hour * 60 + b.minute))

    near_sunrise = _mins(t, sunrise) <= 45
    near_sunset = _mins(t, sunset) <= 45

    if near_sunrise or near_sunset:
        return profile.dawn_dusk_boost
    if profile.low_light_lover and (cond_is_night := (t < sunrise or t > sunset)):
        return 1.10
    return 1.0


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #

def compute_bite_score(cond: HourlyConditions, species_key: str = "general") -> BiteScoreResult:
    profile = get_profile(species_key)

    breakdown = FactorBreakdown(
        pressure=score_pressure(cond.pressure_hpa, cond.pressure_delta_3h, cond.pressure_delta_24h),
        temperature=score_temperature(cond.air_temp_c, profile.temp_band),
        wind=score_wind(cond.wind_speed_kmh),
        water=score_water(cond),
        solunar=score_solunar(cond),
        sky=score_sky(cond),
    )

    weighted_contribution = {
        factor: getattr(breakdown, factor) * weight
        for factor, weight in profile.weights.items()
    }
    raw_score = sum(weighted_contribution.values())

    tod_mult = time_of_day_multiplier(cond.timestamp, cond.sunrise, cond.sunset, profile)
    final_score = max(0.0, min(100.0, raw_score * tod_mult))

    safety_flag = None
    if cond.is_storm:
        # A storm must suppress the *headline* score, not just the sky
        # sub-score — otherwise strong pressure/wind/temperature readings
        # can still add up to a high number while it's actively unsafe to
        # be on the water. Cap it hard rather than letting the weighted
        # blend decide.
        final_score = min(final_score, 15.0)
        safety_flag = "Storm conditions reported — score suppressed; do not fish through lightning."
    elif cond.is_heavy_precip:
        # Heavy rain/snow without lightning: visibility, comfort, and
        # runoff make fishing inadvisable, but it is not the lightning-
        # lethal case — cap above the storm cap so the two stay distinct.
        final_score = min(final_score, 35.0)
        safety_flag = "Heavy precipitation — fishing not recommended this hour."

    return BiteScoreResult(
        timestamp=cond.timestamp,
        score=round(final_score, 1),
        breakdown=breakdown,
        weighted_contribution={k: round(v, 1) for k, v in weighted_contribution.items()},
        time_of_day_multiplier=tod_mult,
        safety_flag=safety_flag,
        precip_probability_pct=cond.precip_probability_pct,
    )


def best_windows(results: list[BiteScoreResult], top_n: int = 3,
                  min_gap_hours: int = 3) -> list[BiteScoreResult]:
    """Pick the top N non-overlapping hourly peaks (so a 7-day forecast
    doesn't just return six consecutive hours of one good afternoon).
    Safety-flagged hours (storm, heavy precip) are never recommended,
    even when every unflagged hour scores lower."""
    ranked = sorted((r for r in results if r.safety_flag is None),
                    key=lambda r: r.score, reverse=True)
    chosen: list[BiteScoreResult] = []
    for r in ranked:
        if all(abs((r.timestamp - c.timestamp).total_seconds()) >= min_gap_hours * 3600
               for c in chosen):
            chosen.append(r)
        if len(chosen) == top_n:
            break
    return sorted(chosen, key=lambda r: r.timestamp)


@dataclass
class PeakWindow:
    start: datetime
    end: datetime
    peak_score: float


def peak_windows(results: list[BiteScoreResult],
                 majors_per_day: int = 2,
                 minors_per_day: int = 2,
                 min_gap_hours: int = 4,
                 tolerance: float = 5.0,
                 max_half_width_hours: int = 1) -> tuple[list[PeakWindow], list[PeakWindow]]:
    """Per-day major/minor time windows derived from the aggregate score
    (not from moon events): clients display these as "Major/Minor times",
    so they always agree with the activity curve.

    Per calendar day, the `majors_per_day` highest hourly peaks (kept
    `min_gap_hours` apart) anchor major windows, the next `minors_per_day`
    anchor minors. Each window expands around its peak hour while
    neighboring hours stay within `tolerance` points of the peak, up to
    `max_half_width_hours` each side, never claiming an hour twice. The
    end is exclusive of the last hour block (an hour point covers
    [t, t+1h)). Windows are relative to each day — a poor day still gets
    its "least bad" windows; the headline score conveys how good they are.

    Defaults are calibrated against how anglers read competitor apps
    (2026-07-16): windows run 1-3 h, and `min_gap_hours` must exceed
    2*max_half_width_hours + 1 so two windows can never touch and merge
    into one half-day block.
    """
    by_day: dict = {}
    for r in results:
        by_day.setdefault(r.timestamp.date(), []).append(r)

    majors: list[PeakWindow] = []
    minors: list[PeakWindow] = []
    for day in sorted(by_day):
        hours = sorted(by_day[day], key=lambda r: r.timestamp)
        ranked = sorted(range(len(hours)), key=lambda i: hours[i].score, reverse=True)
        chosen: list[int] = []
        for i in ranked:
            if all(abs(i - j) >= min_gap_hours for j in chosen):
                chosen.append(i)
            if len(chosen) == majors_per_day + minors_per_day:
                break

        claimed: set[int] = set()
        for rank, i in enumerate(chosen):  # highest peaks claim their hours first
            peak = hours[i].score
            lo = hi = i
            while (lo - 1 >= 0 and i - (lo - 1) <= max_half_width_hours
                   and (lo - 1) not in claimed and hours[lo - 1].score >= peak - tolerance):
                lo -= 1
            while (hi + 1 < len(hours) and (hi + 1) - i <= max_half_width_hours
                   and (hi + 1) not in claimed and hours[hi + 1].score >= peak - tolerance):
                hi += 1
            claimed.update(range(lo, hi + 1))
            window = PeakWindow(start=hours[lo].timestamp,
                                end=hours[hi].timestamp + timedelta(hours=1),
                                peak_score=peak)
            (majors if rank < majors_per_day else minors).append(window)

    return (sorted(majors, key=lambda w: w.start),
            sorted(minors, key=lambda w: w.start))
