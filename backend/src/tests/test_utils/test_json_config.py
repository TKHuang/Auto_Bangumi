"""Unit tests for module.utils.json_config module."""

import json
import pytest

from module.utils.json_config import load, save


class TestJsonConfigLoad:
    """Test cases for load function."""

    def test_load_reads_json_file(self, tmp_path):
        """Test load reads JSON file correctly."""
        test_data = {"key": "value", "number": 42}
        test_file = tmp_path / "test.json"
        
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        
        result = load(str(test_file))
        assert result == test_data

    def test_load_with_nested_dict(self, tmp_path):
        """Test load handles nested dictionaries."""
        test_data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }
        test_file = tmp_path / "nested.json"
        
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        
        result = load(str(test_file))
        assert result == test_data
        assert result["level1"]["level2"]["level3"] == "value"

    def test_load_with_list(self, tmp_path):
        """Test load handles lists."""
        test_data = {"items": [1, 2, 3, "four"]}
        test_file = tmp_path / "list.json"
        
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        
        result = load(str(test_file))
        assert result == test_data

    def test_load_with_unicode(self, tmp_path):
        """Test load handles unicode characters."""
        test_data = {"chinese": "中文", "emoji": "🎉", "japanese": "日本語"}
        test_file = tmp_path / "unicode.json"
        
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False)
        
        result = load(str(test_file))
        assert result == test_data

    def test_load_empty_dict(self, tmp_path):
        """Test load handles empty dictionary."""
        test_data = {}
        test_file = tmp_path / "empty.json"
        
        with open(test_file, "w", encoding="utf-8") as f:
            json.dump(test_data, f)
        
        result = load(str(test_file))
        assert result == {}

    def test_load_file_not_found(self, tmp_path):
        """Test load raises error for non-existent file."""
        test_file = tmp_path / "nonexistent.json"
        
        with pytest.raises(FileNotFoundError):
            load(str(test_file))


class TestJsonConfigSave:
    """Test cases for save function."""

    def test_save_writes_json_file(self, tmp_path):
        """Test save writes JSON file correctly."""
        test_data = {"key": "value", "number": 42}
        test_file = tmp_path / "test.json"
        
        save(str(test_file), test_data)
        
        with open(test_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        
        assert result == test_data

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

    def test_save_nested_dict(self, tmp_path):
        """Test save handles nested dictionaries."""
        test_data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }
        test_file = tmp_path / "nested.json"
        
        save(str(test_file), test_data)
        
        with open(test_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        
        assert result == test_data

    def test_save_with_list(self, tmp_path):
        """Test save handles lists."""
        test_data = {"items": [1, 2, 3, "four"]}
        test_file = tmp_path / "list.json"
        
        save(str(test_file), test_data)
        
        with open(test_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        
        assert result == test_data

    def test_save_empty_dict(self, tmp_path):
        """Test save handles empty dictionary."""
        test_data = {}
        test_file = tmp_path / "empty.json"
        
        save(str(test_file), test_data)
        
        with open(test_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        
        assert result == {}

    def test_save_overwrites_existing_file(self, tmp_path):
        """Test save overwrites existing file."""
        test_file = tmp_path / "test.json"
        
        save(str(test_file), {"old": "data"})
        save(str(test_file), {"new": "data"})
        
        with open(test_file, "r", encoding="utf-8") as f:
            result = json.load(f)
        
        assert result == {"new": "data"}


class TestJsonConfigRoundTrip:
    """Test cases for round-trip save and load."""

    def test_roundtrip_simple_dict(self, tmp_path):
        """Test save then load returns same data."""
        test_data = {"key": "value", "number": 42}
        test_file = tmp_path / "roundtrip.json"
        
        save(str(test_file), test_data)
        result = load(str(test_file))
        
        assert result == test_data

    def test_roundtrip_nested_dict(self, tmp_path):
        """Test round-trip with nested dictionary."""
        test_data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            },
            "list": [1, 2, 3],
            "string": "test"
        }
        test_file = tmp_path / "roundtrip.json"
        
        save(str(test_file), test_data)
        result = load(str(test_file))
        
        assert result == test_data

    def test_roundtrip_unicode(self, tmp_path):
        """Test round-trip with unicode characters."""
        test_data = {
            "chinese": "中文",
            "emoji": "🎉",
            "japanese": "日本語",
            "korean": "한국어"
        }
        test_file = tmp_path / "unicode_roundtrip.json"
        
        save(str(test_file), test_data)
        result = load(str(test_file))
        
        assert result == test_data

    def test_roundtrip_complex_structure(self, tmp_path):
        """Test round-trip with complex nested structure."""
        test_data = {
            "users": [
                {"id": 1, "name": "Alice", "tags": ["admin", "user"]},
                {"id": 2, "name": "Bob", "tags": ["user"]}
            ],
            "settings": {
                "theme": "dark",
                "notifications": True,
                "language": "en"
            },
            "metadata": {
                "version": "1.0",
                "created": "2024-01-01"
            }
        }
        test_file = tmp_path / "complex_roundtrip.json"
        
        save(str(test_file), test_data)
        result = load(str(test_file))
        
        assert result == test_data
