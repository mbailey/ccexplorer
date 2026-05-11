"""Token pricing for Claude models.

Prices are USD per 1,000,000 tokens. Keys:

* ``in``    -- raw input tokens
* ``out``   -- output tokens
* ``cw5m``  -- 5-minute ephemeral cache write
* ``cw1h``  -- 1-hour ephemeral cache write
* ``cr``    -- cache read

The ``family`` function maps a full model id (e.g.
``claude-opus-4-7-20251115``) to one of the three pricing families
(opus / sonnet / haiku). Unknown families default to ``opus`` to fail
loud rather than under-cost silently.
"""
from __future__ import annotations

PRICES: dict[str, dict[str, float]] = {
    "opus":   {"in": 15.00, "out": 75.00, "cw5m": 18.75, "cw1h": 30.00, "cr": 1.50},
    "sonnet": {"in":  3.00, "out": 15.00, "cw5m":  3.75, "cw1h":  6.00, "cr": 0.30},
    "haiku":  {"in":  0.80, "out":  4.00, "cw5m":  1.00, "cw1h":  1.60, "cr": 0.08},
}


def family(model: str) -> str:
    """Return the pricing family for a model id.

    >>> family("claude-opus-4-7-20251115")
    'opus'
    >>> family("claude-sonnet-4-6")
    'sonnet'
    >>> family("unknown-model")
    'opus'
    """
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return "opus"


def cost_for_usage(model: str, usage: dict) -> dict[str, float]:
    """Compute per-bucket cost in USD for a Claude API ``usage`` block.

    Returns a dict with keys ``input``, ``output``, ``cw5``, ``cw1``, ``cr``.
    Missing fields are treated as zero.
    """
    p = PRICES[family(model)]
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cw_total = usage.get("cache_creation_input_tokens", 0) or 0
    cc = usage.get("cache_creation") or {}
    cw5 = cc.get("ephemeral_5m_input_tokens", cw_total) if cc else cw_total
    cw1 = cc.get("ephemeral_1h_input_tokens", 0) if cc else 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    return {
        "input":  inp * p["in"]   / 1_000_000,
        "output": out * p["out"]  / 1_000_000,
        "cw5":    cw5 * p["cw5m"] / 1_000_000,
        "cw1":    cw1 * p["cw1h"] / 1_000_000,
        "cr":     cr  * p["cr"]   / 1_000_000,
    }
