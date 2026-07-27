"""
limits_client.py — regs_advisor.providers
--------------------------------------------
Fetches the catch/possession/length-limit HTML grid for a zone
(confirmed reachable with a plain GET, no session/JS — see
docs/REGS_CHATBOT_PLAN.md Phase 0) and hands it to the pure parser
in regs_advisor.engine.limits.
"""

import httpx

from regs_advisor.engine.limits import ZoneLimits, parse_limits_html

LIMITS_URL = "https://peche.faune.gouv.qc.ca/RegPec/en/Info/Reglements"
_HTTP_TIMEOUT = 15.0


class LimitsLookupError(RuntimeError):
    """Raised when the limits provider is unreachable."""


async def fetch_limits(id_zone: int, zone_name: str) -> ZoneLimits:
    params = {"id_zone": id_zone, "resultats": "True"}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        try:
            resp = await client.get(LIMITS_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise LimitsLookupError(f"limits provider unreachable: {e}") from e

    return parse_limits_html(resp.text, zone_name=zone_name)
