"""Backend↔frontend contract.

A single place that declares the shape of every API response and labels its data
source. Previously the frontend knew field names by heart and no number said where
it came from — a renamed field would break the UI silently. Now:

  * every response is wrapped in an envelope carrying an `api_version` and a
    `source` (live | cached | illustrative), so the UI can be honest about what is
    real, what is precomputed and what is a placeholder;
  * declared endpoints are checked against their required keys, so contract drift is
    caught loudly on the server instead of showing up as a blank panel.

Illustrative research simulation — most numbers are placeholders by design.
"""
from __future__ import annotations

API_VERSION = "1.0"

# Required top-level keys per endpoint. Drift from these (e.g. a renamed field) is
# surfaced as a contract_warning in the response instead of silently breaking the UI.
REQUIRED = {
    "/api/locomotion": ["frames", "metrics"],
    "/api/autonomic": ["points", "metrics"],
    "/api/sensors": ["series", "state", "metrics"],
    "/api/programs": ["programs", "summary", "mapping"],
    "/api/guardian": ["none", "reactive", "predictive"],
    "/api/gym": ["benchmark", "twin"],
    "/api/proposal": ["proposal", "log"],
    "/api/unified": ["evidence", "gait_frames"],
}


def check_contract(name: str, payload) -> str | None:
    """Return a human-readable warning if the payload is missing declared keys."""
    req = REQUIRED.get(name)
    if not req or not isinstance(payload, dict):
        return None
    missing = [k for k in req if k not in payload]
    return ("missing keys: " + ", ".join(missing)) if missing else None


def envelope(payload, source: str = "illustrative", warning: str | None = None) -> dict:
    """Wrap a payload with contract metadata. Non-breaking: existing keys are kept at
    the top level, metadata is added under `_meta`."""
    meta = {"api_version": API_VERSION, "source": source}
    if warning:
        meta["contract_warning"] = warning
    if isinstance(payload, dict):
        return {**payload, "_meta": meta}
    return {"data": payload, "_meta": meta}
