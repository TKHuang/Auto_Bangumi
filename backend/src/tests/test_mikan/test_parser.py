"""Parser tests for Mikan episode pages (spec §8.1)."""
from pathlib import Path

import pytest

from module.mikan.parser import MikanRef, parse_mikan_page

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
