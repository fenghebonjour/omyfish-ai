"""
solunar.py — bite_prediction.engine
------------------------------------
Turns solunar event instants (moon transit/antitransit = major,
moonrise/moonset = minor) into the display time-windows clients show as
"Major times" / "Minor times". The event instants themselves come from
the provider layer (ephem astronomy in providers/weather_client.py);
this module is pure datetime math, unit-testable without network.

Window widths mirror the influence spans score_solunar() already models
(major influence decays to zero at 120 min from the event, minor at
60 min): the display window keeps the strong middle of each span —
transit ±75 min (2.5 h), rise/set ±45 min (1.5 h).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

MAJOR_HALF_WIDTH_MIN = 75
MINOR_HALF_WIDTH_MIN = 45


@dataclass
class SolunarWindow:
    start: datetime
    end: datetime


def build_solunar_windows(event_times: list[datetime], half_width_min: int) -> list[SolunarWindow]:
    """One window per event, centered on it, sorted chronologically."""
    half = timedelta(minutes=half_width_min)
    return [SolunarWindow(t - half, t + half) for t in sorted(event_times)]
