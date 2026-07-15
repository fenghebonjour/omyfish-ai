from datetime import datetime, time, timedelta
from bite_score import HourlyConditions, compute_bite_score, best_windows

base = datetime(2026, 7, 15, 5, 0)

samples = []
for h in range(0, 24):
    ts = base + timedelta(hours=h)
    falling = -1.5 if 4 <= h <= 9 else 0.2
    samples.append(HourlyConditions(
        timestamp=ts,
        air_temp_c=18 + 6 * (0.5 - abs(0.5 - h / 24)),
        feels_like_c=18,
        pressure_hpa=1015 + h * 0.1,
        pressure_delta_3h=falling,
        pressure_delta_24h=-2.0,
        wind_speed_kmh=10,
        cloud_cover_pct=60,
        precip_mm=0,
        is_storm=False,
        moon_phase=0.02,
        minutes_from_moon_major=abs(h - 6) * 60,
        minutes_from_moon_minor=abs(h - 18) * 60,
        lake_level_trend_cm_per_day=2,
        tide_rate_m_per_hr=None,
        sunrise=time(5, 30),
        sunset=time(20, 45),
    ))

results = [compute_bite_score(c, species_key="smallmouth_bass") for c in samples]
for r in results:
    print(r.timestamp.strftime("%H:%M"), r.score, r.breakdown.as_dict(), "x", r.time_of_day_multiplier)

print("\nTop windows:")
for r in best_windows(results, top_n=3):
    print(r.timestamp.strftime("%H:%M"), r.score, r.weighted_contribution)
