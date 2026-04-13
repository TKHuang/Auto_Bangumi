"""Tests for save path generation and sanitization."""

import pytest

from module.domain.value_objects import gen_save_path, sanitize_path_component


class TestSanitizePathComponent:
    """sanitize_path_component must replace filesystem-illegal chars."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("plain", "plain"),
            ("title?", "title？"),
            ("a:b", "a：b"),
            ("a*b", "a＊b"),
            ("<>|\"", "＜＞｜＂"),
            ("path/with\\slash", "path／with＼slash"),
            ("trailing dots...", "trailing dots"),
            ("   ", "_"),
            ("", "_"),
        ],
    )
    def test_sanitize(self, raw, expected):
        assert sanitize_path_component(raw) == expected


class TestGenSavePath:
    """gen_save_path must produce PikPak-safe paths."""

    def test_basic(self):
        assert gen_save_path("/downloads", "Anime", 1) == "/downloads/Anime/Season 1"

    def test_strips_question_mark(self):
        """Regression: bangumi 88 production bug — title ending in ``?``
        caused PikPak ``The name contains illegal characters`` error."""
        title = "最强的职业不是勇者也不是贤者好像是鉴定士(伪)的样子?"
        path = gen_save_path("/downloads/Bangumi", title, 1)
        assert "?" not in path
        assert "？" in path
        assert path.endswith("/Season 1")

    def test_year_included(self):
        assert gen_save_path("/d", "Anime", 2, year="2024") == "/d/Anime (2024)/Season 2"

    def test_year_with_illegal_title(self):
        path = gen_save_path("/d", "X:Y?", 1, year="2024")
        assert path == "/d/X：Y？ (2024)/Season 1"
