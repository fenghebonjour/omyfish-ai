"""
calibration.py
--------------
ROADMAP — not wired up yet. Sketches how OMyFish upgrades from
hand-tuned weights (species_profiles.py) to weights learned from real
catch outcomes, WITHOUT losing explainability.

Why this design instead of a black-box model from day one:
  - Cold start: a new species/region has zero catch logs. The
    hand-tuned profile is the only thing that works on day one.
  - Trust: reviewers already call competitor "AI forecasts" a black
    box. Replacing hand-tuned weights outright with a neural net would
    repeat that mistake even if it's more accurate.
  - Data volume: logistic regression on 6 features needs comparatively
    few labeled trips to become reliable per region/species — a deep
    model would overfit long before that.

Plan:
  1. Every logged catch (or logged blank trip, which matters just as
     much) is stored with the HourlyConditions that were active at
     that time and location — this is just persisting the same struct
     bite_score.py already computes on, no new pipeline needed.
  2. Once a region/species pair crosses a minimum sample size
     (proposed: 200 trips, split fished/blank), fit a simple logistic
     regression: outcome ~ pressure + temperature + wind + water +
     solunar + sky (the six sub-scores from FactorBreakdown, not the
     raw weather features — this keeps the learned layer a re-weighting
     of the same six interpretable factors, not a replacement of them).
  3. The fitted coefficients become that region/species' weight
     override — still stored as plain numbers in the same shape as
     SpeciesProfile.weights, still inspectable, still overridable by a
     biologist if the data is thin or biased (e.g. anglers
     over-reporting good days).
  4. Ship the override with a confidence/sample-size badge in the API
     response so the app can show "Tuned from 412 local trips" vs.
     "Default model" — turning the calibration process itself into a
     transparency feature rather than hiding it.

class CalibratedWeights (sketch — not implemented):
    region_id: str
    species_key: str
    weights: dict[str, float]      # same 6 keys as SpeciesProfile.weights
    sample_size: int
    fitted_at: datetime
    r_squared_or_auc: float        # shown to the user as a confidence signal

This module intentionally ships as pseudocode/plan rather than a live
sklearn dependency: the six-factor breakdown must be validated against
real catch logs from the closed beta first, so the shape of the labeled
dataset (and therefore the exact fitting code) shouldn't be locked in
before that data exists.
"""
