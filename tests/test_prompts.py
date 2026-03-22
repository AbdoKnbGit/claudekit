"""Tests for claudekit.prompts -- PromptManager, PromptVersion, ComparisonResult."""

import pytest

from claudekit.prompts._comparison import ComparisonResult
from claudekit.prompts._manager import PromptManager
from claudekit.prompts._version import PromptVersion


# ── PromptVersion ────────────────────────────────────────────────────────── #


class TestPromptVersion:
    def test_creation(self):
        pv = PromptVersion(name="support", version="1.0", system="Be helpful.")
        assert pv.name == "support"
        assert pv.version == "1.0"
        assert pv.system == "Be helpful."
        assert pv.user_template == ""
        assert pv.metadata == {}

    def test_render(self):
        pv = PromptVersion(
            name="support",
            version="1.0",
            system="System.",
            user_template="Hello {name}, your order #{order_id}.",
        )
        result = pv.render(name="Alice", order_id="123")
        assert result == "Hello Alice, your order #123."

    def test_render_no_template(self):
        pv = PromptVersion(name="x", version="1", system="s")
        assert pv.render() == ""

    def test_to_dict_roundtrip(self):
        pv = PromptVersion(
            name="support",
            version="2.0",
            system="Be concise.",
            user_template="Hi {name}",
            metadata={"author": "test"},
        )
        d = pv.to_dict()
        restored = PromptVersion.from_dict(d)
        assert restored.name == pv.name
        assert restored.version == pv.version
        assert restored.system == pv.system
        assert restored.user_template == pv.user_template
        assert restored.metadata == pv.metadata


# ── ComparisonResult ─────────────────────────────────────────────────────── #


class TestComparisonResult:
    def test_creation(self):
        cr = ComparisonResult(
            versions=["1.0", "2.0"],
            inputs=["input1", "input2"],
        )
        assert cr.versions == ["1.0", "2.0"]
        assert cr.inputs == ["input1", "input2"]
        assert cr.outputs == {}
        assert cr.costs == {}

    def test_to_csv(self):
        cr = ComparisonResult(
            versions=["1.0", "2.0"],
            inputs=["hello"],
            outputs={"1.0": ["resp1"], "2.0": ["resp2"]},
        )
        csv = cr.to_csv()
        assert "1.0" in csv
        assert "2.0" in csv
        assert "hello" in csv
        assert "resp1" in csv


# ── PromptManager ────────────────────────────────────────────────────────── #


@pytest.fixture
def pm(tmp_path):
    """Create a PromptManager with a temp storage file."""
    return PromptManager(storage_path=tmp_path / "prompts.json")


class TestPromptManager:
    def test_save_and_load(self, pm):
        pm.save("support", "Be concise.", version="1.0")
        pv = pm.load("support", "1.0")
        assert pv is not None
        assert pv.system == "Be concise."

    def test_load_latest(self, pm):
        pm.save("support", "Version 1", version="1.0")
        pm.save("support", "Version 2", version="2.0")
        pv = pm.load("support", "latest")
        assert pv is not None
        # Latest should be the most recently saved
        assert pv.version == "2.0"

    def test_load_missing(self, pm):
        assert pm.load("nonexistent") is None

    def test_list_versions(self, pm):
        pm.save("support", "V1", version="1.0")
        pm.save("support", "V2", version="2.0")
        versions = pm.list("support")
        assert len(versions) == 2

    def test_delete(self, pm):
        pm.save("support", "V1", version="1.0")
        assert pm.delete("support", "1.0") is True
        assert pm.load("support", "1.0") is None
        assert pm.delete("support", "1.0") is False

    def test_diff(self, pm):
        pm.save("support", "Be concise.", version="1.0")
        pm.save("support", "Be concise and empathetic.", version="2.0")
        diff = pm.diff("support", "1.0", "2.0")
        assert "---" in diff  # unified diff header
        assert "+++" in diff

    def test_diff_missing_version_raises(self, pm):
        pm.save("support", "V1", version="1.0")
        with pytest.raises(ValueError, match="not found"):
            pm.diff("support", "1.0", "999.0")

    def test_render(self, pm):
        pm.save(
            "support",
            "System prompt",
            version="1.0",
            user_template="Hello {user}!",
        )
        result = pm.render("support", "1.0", user="Alice")
        assert result == "Hello Alice!"

    def test_render_missing_raises(self, pm):
        with pytest.raises(ValueError, match="not found"):
            pm.render("missing", "1.0")

    def test_export_import(self, pm, tmp_path):
        pm.save("support", "V1", version="1.0")
        pm.save("support", "V2", version="2.0")
        exported = pm.export("support")
        assert exported["name"] == "support"
        assert len(exported["versions"]) == 2

        pm2 = PromptManager(storage_path=tmp_path / "prompts2.json")
        pm2.import_(exported)
        pv = pm2.load("support", "1.0")
        assert pv is not None
        assert pv.system == "V1"

    def test_save_with_metadata(self, pm):
        pv = pm.save("support", "V1", version="1.0", metadata={"author": "test"})
        assert pv.metadata == {"author": "test"}
