"""Unit tests for score-derived major/minor peak windows — pure functions."""

from datetime import datetime, timedelta

from bite_prediction.engine import peak_windows
from bite_prediction.engine.bite_score import BiteScoreResult, FactorBreakdown


def _result(ts: datetime, score: float) -> BiteScoreResult:
    return BiteScoreResult(
        timestamp=ts, score=score,
        breakdown=FactorBreakdown(50, 50, 50, 50, 50, 50),
        weighted_contribution={}, time_of_day_multiplier=1.0,
    )


def _day(scores: list[float], day: datetime = datetime(2026, 7, 16)) -> list[BiteScoreResult]:
    return [_result(day + timedelta(hours=h), s) for h, s in enumerate(scores)]


def _scores_with_peaks() -> list[float]:
    """24 hourly scores: peaks at 5h (83), 15h (74), 20h (60), 10h (55)."""
    scores = [30.0] * 24
    scores[3], scores[4], scores[5], scores[6], scores[7] = 60, 76, 83, 75, 50
    scores[14], scores[15], scores[16] = 70, 74, 66
    scores[20] = 60
    scores[10] = 55
    return scores


def test_top_two_peaks_become_majors_next_two_minors():
    majors, minors = peak_windows(_day(_scores_with_peaks()))
    assert len(majors) == 2 and len(minors) == 2
    major_peaks = {w.peak_score for w in majors}
    assert major_peaks == {83.0, 74.0}
    assert {w.peak_score for w in minors} == {60.0, 55.0}


def test_window_expands_only_within_tolerance_of_peak():
    majors, _ = peak_windows(_day(_scores_with_peaks()))
    best = next(w for w in majors if w.peak_score == 83.0)
    # neighbors 76 and 75 are within 10 pts of 83; 60 (3h) and 50 (7h) are not
    assert best.start == datetime(2026, 7, 16, 4, 0)
    assert best.end == datetime(2026, 7, 16, 7, 0)  # last hour block [6h, 7h)


def test_windows_do_not_overlap():
    majors, minors = peak_windows(_day(_scores_with_peaks()))
    windows = sorted(majors + minors, key=lambda w: w.start)
    for earlier, later in zip(windows, windows[1:]):
        assert earlier.end <= later.start


def test_each_day_gets_its_own_windows():
    two_days = _day(_scores_with_peaks()) + _day(
        _scores_with_peaks(), day=datetime(2026, 7, 17)
    )
    majors, minors = peak_windows(two_days)
    assert len(majors) == 4 and len(minors) == 4
    assert {w.start.date().isoformat() for w in majors} == {"2026-07-16", "2026-07-17"}
