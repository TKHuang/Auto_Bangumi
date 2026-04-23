"""Parser tests for Mikan episode pages (spec §8.1)."""
from pathlib import Path

import pytest

from module.mikan.parser import (
    MikanRef,
    build_canonical_bangumi_url,
    parse_canonical_bangumi_url,
    parse_mikan_page,
)

_FIX = Path(__file__).parent.parent / "fixtures" / "mikan"


def _load(name: str) -> str:
    return (_FIX / name).read_text(encoding="utf-8")


@pytest.mark.unit
class TestParseMikanPage:
    def test_tier_a_subscribe_button(self):
        html = _load("episode_page_subscribe_button.html")
        ref = parse_mikan_page(html)
        assert ref == MikanRef(
            mikan_bangumi_id=3906,
            mikan_subgroup_id=370,
            canonical_title="身为悲剧始作俑者的最强邪恶BOSS女王为民竭心尽力。 第二季",
            poster_url="/images/Bangumi/202410/730372c2.jpg",
        )

    def test_tier_b_anchor_only(self):
        html = _load("episode_page_anchor_only.html")
        ref = parse_mikan_page(html)
        assert ref is not None
        assert ref.mikan_bangumi_id == 1234
        assert ref.mikan_subgroup_id == 77
        assert ref.canonical_title == "葬送的芙莉蓮"
        assert ref.poster_url == "/images/Bangumi/202309/frieren.jpg"

    def test_tier_c_rss_link_only(self):
        html = _load("episode_page_rss_link_only.html")
        ref = parse_mikan_page(html)
        assert ref is not None
        assert ref.mikan_bangumi_id == 5555
        assert ref.mikan_subgroup_id == 99
        assert ref.poster_url is None or isinstance(ref.poster_url, str)

    def test_title_wrapped_in_p_tag(self):
        html = (
            '<html><body>'
            '<a class="js-subscribe-bangumi" data-bangumiid="42" data-subtitlegroupid="7">sub</a>'
            '<p class="bangumi-title">\n'
            '  <a href="/Home/Bangumi/42">玩命邪神</a>\n'
            '</p>'
            '</body></html>'
        )
        ref = parse_mikan_page(html)
        assert ref is not None
        assert ref.canonical_title == "玩命邪神"

    def test_title_with_html_entities(self):
        # Real Mikan pages encode CJK characters as numeric HTML entities.
        html = (
            '<html><body>'
            '<a class="js-subscribe-bangumi" data-bangumiid="1" data-subtitlegroupid="1">sub</a>'
            '<p class="bangumi-title"><a href="/Home/Bangumi/1">'
            '&#x59EC;&#x9A91;&#x58EB;&#x662F;&#x86EE;&#x65CF;&#x7684;&#x65B0;&#x5A18;'
            '</a></p>'
            '</body></html>'
        )
        ref = parse_mikan_page(html)
        assert ref is not None
        assert ref.canonical_title == "姬骑士是蛮族的新娘"

    def test_no_ref_returns_none(self):
        html = _load("episode_page_no_ref.html")
        assert parse_mikan_page(html) is None

    def test_empty_input_returns_none(self):
        assert parse_mikan_page("") is None

    def test_prefers_tier_a_over_tier_b_when_both_present(self):
        html = (
            '<html><body>'
            '<a class="js-subscribe-bangumi" data-bangumiid="100" data-subtitlegroupid="1">sub</a>'
            '<a href="/Home/Bangumi/999#2">other</a>'
            '</body></html>'
        )
        ref = parse_mikan_page(html)
        assert ref is not None
        assert ref.mikan_bangumi_id == 100
        assert ref.mikan_subgroup_id == 1


@pytest.mark.unit
class TestCanonicalBangumiUrl:
    def test_build_returns_default_host_form(self):
        url = build_canonical_bangumi_url(3901, 1243)
        assert url == "https://mikanani.me/Home/Bangumi/3901#1243"

    def test_build_accepts_custom_base_url(self):
        url = build_canonical_bangumi_url(
            3901, 1243, base_url="https://mikanime.tv/"
        )
        assert url == "https://mikanime.tv/Home/Bangumi/3901#1243"

    def test_build_rejects_non_positive_bangumi_id(self):
        with pytest.raises(ValueError):
            build_canonical_bangumi_url(0, 1243)
        with pytest.raises(ValueError):
            build_canonical_bangumi_url(-1, 1243)

    def test_build_rejects_non_positive_subgroup_id(self):
        with pytest.raises(ValueError):
            build_canonical_bangumi_url(3901, 0)
        with pytest.raises(ValueError):
            build_canonical_bangumi_url(3901, -5)

    def test_parse_roundtrips_build_output(self):
        url = build_canonical_bangumi_url(3901, 1243)
        assert parse_canonical_bangumi_url(url) == (3901, 1243)

    def test_parse_accepts_path_only_input(self):
        assert parse_canonical_bangumi_url(
            "/Home/Bangumi/42#7"
        ) == (42, 7)

    def test_parse_tolerates_surrounding_whitespace(self):
        assert parse_canonical_bangumi_url(
            "   https://mikanani.me/Home/Bangumi/1#2   "
        ) == (1, 2)

    def test_parse_rejects_url_missing_subgroup_fragment(self):
        assert parse_canonical_bangumi_url(
            "https://mikanani.me/Home/Bangumi/3901"
        ) is None

    def test_parse_rejects_non_bangumi_path(self):
        assert parse_canonical_bangumi_url(
            "https://mikanani.me/Home/Episode/0738c550"
        ) is None

    def test_parse_returns_none_for_empty_input(self):
        assert parse_canonical_bangumi_url(None) is None
        assert parse_canonical_bangumi_url("") is None
        assert parse_canonical_bangumi_url("   ") is None
