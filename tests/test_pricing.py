"""Tests for ccexplorer.pricing."""
from __future__ import annotations

import pytest

from ccexplorer.pricing import PRICES, cost_for_usage, family


class TestFamily:
    def test_opus_variants(self):
        assert family("claude-opus-4-7-20251115") == "opus"
        assert family("opus") == "opus"
        assert family("Claude-OPUS-4-6") == "opus"

    def test_sonnet_variants(self):
        assert family("claude-sonnet-4-6") == "sonnet"
        assert family("anthropic.claude-sonnet-3-7") == "sonnet"

    def test_haiku_variants(self):
        assert family("claude-haiku-3-5") == "haiku"

    def test_unknown_defaults_to_opus(self):
        # Fail-loud: unknown models cost the most, so a hidden cheap-model
        # bug surfaces as obvious overcounting rather than silent undercounting.
        assert family("gpt-4") == "opus"
        assert family("") == "opus"


class TestPricesTable:
    def test_all_families_present(self):
        assert set(PRICES) == {"opus", "sonnet", "haiku"}

    def test_all_buckets_present(self):
        for fam, prices in PRICES.items():
            assert set(prices) == {"in", "out", "cw5m", "cw1h", "cr"}

    def test_opus_more_expensive_than_sonnet(self):
        # Sanity: opus output should always cost more than sonnet output, etc.
        for bucket in ("in", "out", "cw5m", "cw1h", "cr"):
            assert PRICES["opus"][bucket] > PRICES["sonnet"][bucket], bucket
            assert PRICES["sonnet"][bucket] > PRICES["haiku"][bucket], bucket

    def test_cache_read_cheapest(self):
        for prices in PRICES.values():
            assert prices["cr"] < prices["in"]
            assert prices["cr"] < prices["cw5m"]


class TestCostForUsage:
    def test_pure_input(self):
        c = cost_for_usage("claude-opus-4-7", {"input_tokens": 1_000_000})
        assert c == {"input": 15.0, "output": 0.0, "cw5": 0.0, "cw1": 0.0, "cr": 0.0}

    def test_pure_output(self):
        c = cost_for_usage("claude-opus-4-7", {"output_tokens": 1_000_000})
        assert c == {"input": 0.0, "output": 75.0, "cw5": 0.0, "cw1": 0.0, "cr": 0.0}

    def test_pure_cache_read(self):
        c = cost_for_usage("claude-opus-4-7", {"cache_read_input_tokens": 1_000_000})
        assert c == {"input": 0.0, "output": 0.0, "cw5": 0.0, "cw1": 0.0, "cr": 1.5}

    def test_empty_usage(self):
        c = cost_for_usage("claude-opus-4-7", {})
        assert sum(c.values()) == 0.0

    def test_none_values_treated_as_zero(self):
        c = cost_for_usage(
            "claude-opus-4-7",
            {"input_tokens": None, "output_tokens": 100, "cache_read_input_tokens": None},
        )
        assert c["input"] == 0.0
        assert c["output"] == pytest.approx(100 * 75 / 1_000_000)
        assert c["cr"] == 0.0

    def test_cache_creation_dict_takes_precedence(self):
        # When the structured cache_creation dict is present, its
        # ephemeral_5m_input_tokens / ephemeral_1h_input_tokens replace
        # the flat cache_creation_input_tokens for the 5m/1h split.
        c = cost_for_usage(
            "claude-sonnet-4-6",
            {
                "cache_creation_input_tokens": 1_000_000,
                "cache_creation": {
                    "ephemeral_5m_input_tokens": 600_000,
                    "ephemeral_1h_input_tokens": 400_000,
                },
            },
        )
        # 600k @ 3.75 + 400k @ 6.00 per million
        assert c["cw5"] == pytest.approx(600_000 * 3.75 / 1_000_000)
        assert c["cw1"] == pytest.approx(400_000 * 6.00 / 1_000_000)

    def test_cache_creation_absent_falls_back_to_flat(self):
        # When cache_creation dict is missing, the flat
        # cache_creation_input_tokens flows entirely into the 5m bucket.
        c = cost_for_usage("claude-sonnet-4-6", {"cache_creation_input_tokens": 1_000_000})
        assert c["cw5"] == pytest.approx(3.75)
        assert c["cw1"] == 0.0

    def test_mixed_usage_sums_correctly(self):
        c = cost_for_usage(
            "claude-opus-4-7",
            {
                "input_tokens": 100_000,
                "output_tokens": 50_000,
                "cache_read_input_tokens": 200_000,
                "cache_creation_input_tokens": 30_000,
            },
        )
        # opus: in 15, out 75, cr 1.5, cw5m 18.75 -- all per million
        expected = (
            100_000 * 15.00 / 1_000_000
            + 50_000 * 75.00 / 1_000_000
            + 200_000 * 1.50 / 1_000_000
            + 30_000 * 18.75 / 1_000_000
        )
        assert sum(c.values()) == pytest.approx(expected)

    def test_unknown_model_uses_opus_pricing(self):
        c_unknown = cost_for_usage("future-model", {"input_tokens": 1_000_000})
        c_opus = cost_for_usage("claude-opus-4-7", {"input_tokens": 1_000_000})
        assert c_unknown == c_opus
