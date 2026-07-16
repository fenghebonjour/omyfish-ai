"""Unit tests for the solunar display-window builder — pure datetime math."""

from datetime import datetime, timedelta

from bite_prediction.engine import (
    MAJOR_HALF_WIDTH_MIN, MINOR_HALF_WIDTH_MIN, build_solunar_windows,
)


def test_windows_are_centered_on_events_with_correct_width():
    event = datetime(2026, 7, 16, 13, 39)
    [window] = build_solunar_windows([event], MAJOR_HALF_WIDTH_MIN)
    assert window.start == event - timedelta(minutes=75)
    assert window.end == event + timedelta(minutes=75)
    assert window.end - window.start == timedelta(minutes=2 * MAJOR_HALF_WIDTH_MIN)


def test_minor_windows_are_narrower_than_major():
    event = datetime(2026, 7, 16, 7, 53)
    [minor] = build_solunar_windows([event], MINOR_HALF_WIDTH_MIN)
    [major] = build_solunar_windows([event], MAJOR_HALF_WIDTH_MIN)
    assert (minor.end - minor.start) < (major.end - major.start)


def test_windows_come_back_sorted_even_if_events_are_not():
    events = [
        datetime(2026, 7, 17, 2, 5),
        datetime(2026, 7, 16, 14, 10),
        datetime(2026, 7, 16, 1, 45),
    ]
    windows = build_solunar_windows(events, MINOR_HALF_WIDTH_MIN)
    starts = [w.start for w in windows]
    assert starts == sorted(starts)
    assert len(windows) == 3
