"""Unit tests for module.utils.json_config module."""

import json
import pytest

from module.utils.json_config import load, save


class TestJsonConfigLoad:
    """Test cases for load function."""

    def test_load_file_not_found(self, tmp_path):
        """Test load raises error for non-existent file."""
        test_file = tmp_path / "nonexistent.json"
        
        with pytest.raises(FileNotFoundError):
            load(str(test_file))


class TestJsonConfigSave:
    """Test cases for save function."""

    def test_save_uses_indent_4(self, tmp_path):
        """Test save uses indent=4 for formatting."""
        test_data = {"key": "value"}
        test_file = tmp_path / "test.json"
        
        save(str(test_file), test_data)
        
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "    " in content

    def test_save_uses_ensure_ascii_false(self, tmp_path):
        """Test save uses ensure_ascii=False for unicode."""
        test_data = {"chinese": "中文", "emoji": "🎉"}
        test_file = tmp_path / "unicode.json"
        
        save(str(test_file), test_data)
        
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        assert "中文" in content
        assert "🎉" in content

    def test_save_overwrites_existing_file(self, tmp_path):
        """Test save overwrites existing file."""
        test_file = tmp_path / "test.json"
        
        save(str(test_file), {"old": "data"})
        save(str(test_file), {"new": "data"})
        
        with open(test_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        
        assert result == {"new": "data"}


class TestJsonConfigRoundTrip:
    """Test cases for round-trip save and load (exercises both functions for each data shape)."""

    @pytest.mark.parametrize(
        "test_data",
        [
            pytest.param({"key": "value", "number": 42}, id="simple"),
            pytest.param(
                {"level1": {"level2": {"level3": "value"}}, "list": [1, 2, 3], "string": "test"},
                id="nested",
            ),
            pytest.param({"items": [1, 2, 3, "four"]}, id="list"),
            pytest.param(
                {"chinese": "中文", "emoji": "🎉", "japanese": "日本語", "korean": "한국어"},
                id="unicode",
            ),
            pytest.param({}, id="empty"),
        ],
    )
    def test_roundtrip(self, tmp_path, test_data):
        """Test save then load returns the same data, for a range of data shapes."""
        test_file = tmp_path / "roundtrip.json"

        save(str(test_file), test_data)
        result = load(str(test_file))

        assert result == test_data
