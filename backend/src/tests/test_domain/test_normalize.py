"""Tests for title normalization (spec §7)."""
import pytest

from module.domain.text.normalize import normalize_title


@pytest.mark.unit
class TestNormalizeTitle:
    def test_trad_simp_chinese_match(self):
        n_trad, _ = normalize_title("葬送的芙莉蓮")
        n_simp, _ = normalize_title("葬送的芙莉莲")
        assert n_trad == n_simp

    def test_fullwidth_halfwidth_match(self):
        n_full, _ = normalize_title("Re：从零开始的异世界生活 第二季")
        n_half, _ = normalize_title("Re:從零開始的異世界生活 第二季")
        assert n_full == n_half

    def test_season_marker_stripped_for_chinese(self):
        n1, _ = normalize_title("我推的孩子 第三季")
        n2, _ = normalize_title("【我推的孩子】 第三季")
        assert n1 == n2

    def test_season_marker_stripped_for_english(self):
        n_en, _ = normalize_title("Re:Zero Season 2")
        n_s2, _ = normalize_title("Re:Zero S2")
        assert "season" not in n_en
        assert "s2" not in n_s2

    def test_cour_part_latter(self):
        _, cour = normalize_title("Re：从零开始的异世界生活 第二季 后半部分")
        assert cour == "latter"

    def test_cour_part_former(self):
        _, cour = normalize_title("Re：从零开始的异世界生活 第二季 前半部分")
        assert cour == "former"

    def test_cour_part_part_n(self):
        _, cour = normalize_title("Series Name Part 2")
        assert cour == "part"

    def test_cour_part_none_default(self):
        _, cour = normalize_title("葬送的芙莉蓮")
        assert cour is None

    def test_brackets_are_stripped(self):
        n1, _ = normalize_title("【我推的孩子】 第三季")
        n2, _ = normalize_title("我推的孩子 第三季")
        assert n1 == n2

    def test_zhuzhu_trad_simp_match(self):
        n_trad, _ = normalize_title("咒術迴戰")
        n_simp, _ = normalize_title("咒术回战")
        assert n_trad == n_simp

    def test_cour_and_season_together(self):
        a, cour_a = normalize_title("Re：从零开始的异世界生活 第二季 后半部分")
        b, cour_b = normalize_title("Re：从零开始的异世界生活 第二季")
        assert a == b
        assert cour_a == "latter"
        assert cour_b is None

    def test_empty_string(self):
        n, cour = normalize_title("")
        assert n == ""
        assert cour is None

    def test_all_whitespace(self):
        n, cour = normalize_title("   ")
        assert n == ""
        assert cour is None

    def test_lowercase_latin(self):
        n_upper, _ = normalize_title("Fate")
        n_lower, _ = normalize_title("fate")
        assert n_upper == n_lower
