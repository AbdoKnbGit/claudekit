"""Tests for claudekit.models -- model registry and cost estimation."""

import pytest

from claudekit.models._registry import (
    MODELS,
    MODELS_BY_ID,
    MODELS_BY_NAME,
    Model,
    get_model,
)


class TestModelDataclass:
    def test_estimate_cost_input_only(self):
        model = Model(
            name="Test",
            api_id="test-model",
            input_per_mtok=3.0,
            output_per_mtok=15.0,
        )
        cost = model.estimate_cost(1_000_000, 0)
        assert cost == pytest.approx(3.0)

    def test_estimate_cost_output_only(self):
        model = Model(
            name="Test",
            api_id="test-model",
            input_per_mtok=3.0,
            output_per_mtok=15.0,
        )
        cost = model.estimate_cost(0, 1_000_000)
        assert cost == pytest.approx(15.0)

    def test_estimate_cost_mixed(self):
        model = Model(
            name="Test",
            api_id="test-model",
            input_per_mtok=3.0,
            output_per_mtok=15.0,
            cache_read_per_mtok=0.3,
            cache_write_per_mtok=3.75,
        )
        cost = model.estimate_cost(1000, 500, cache_read_tokens=200, cache_write_tokens=100)
        expected = (
            1000 * 3.0 / 1e6
            + 500 * 15.0 / 1e6
            + 200 * 0.3 / 1e6
            + 100 * 3.75 / 1e6
        )
        assert cost == pytest.approx(expected)

    def test_estimate_cost_zero(self):
        model = Model(name="Test", api_id="test-model")
        assert model.estimate_cost(0, 0) == 0.0

    def test_fits_in_context_within(self):
        model = Model(name="Test", api_id="test-model", context_window=200_000)
        assert model.fits_in_context(100_000) is True

    def test_fits_in_context_exact(self):
        model = Model(name="Test", api_id="test-model", context_window=200_000)
        assert model.fits_in_context(200_000) is True

    def test_fits_in_context_exceeds(self):
        model = Model(name="Test", api_id="test-model", context_window=200_000)
        assert model.fits_in_context(200_001) is False

    def test_frozen(self):
        model = Model(name="Test", api_id="test-model")
        with pytest.raises(AttributeError):
            model.name = "Changed"


class TestRegistry:
    def test_models_list_populated(self):
        assert len(MODELS) >= 3

    def test_models_by_id_lookup(self):
        for model in MODELS:
            assert model.api_id in MODELS_BY_ID
            assert MODELS_BY_ID[model.api_id] is model

    def test_models_by_name_lookup(self):
        for model in MODELS:
            assert model.name in MODELS_BY_NAME
            assert MODELS_BY_NAME[model.name] is model

    def test_get_model_found(self):
        model = get_model("claude-haiku-4-5")
        assert model is not None
        assert model.api_id == "claude-haiku-4-5"

    def test_get_model_not_found(self):
        assert get_model("nonexistent-model") is None

    def test_haiku_pricing(self):
        haiku = get_model("claude-haiku-4-5")
        assert haiku is not None
        assert haiku.input_per_mtok == 1.0
        assert haiku.output_per_mtok == 5.0

    def test_all_models_have_required_fields(self):
        for model in MODELS:
            assert model.name
            assert model.api_id
            assert model.context_window > 0
            assert model.max_output_tokens > 0
            assert model.input_per_mtok >= 0
            assert model.output_per_mtok >= 0
