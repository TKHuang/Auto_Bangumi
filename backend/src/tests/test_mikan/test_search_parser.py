"""Parser tests for the Mikan search page and bangumi page."""
from pathlib import Path

import pytest

from module.mikan.parser import (
    MikanSearchHit,
    MikanSubgroup,
    parse_mikan_bangumi_subgroups,
    parse_mikan_search_page,
)

_FIX = Path(__file__).parent.parent / "fixtures" / "mikan"


def _load(name: str) -> str:
    return (_FIX / name).read_text(encoding="utf-8")


@pytest.mark.unit
class TestParseMikanSearchPage:
    def test_lists_every_bangumi_in_page_order(self):
        hits = parse_mikan_search_page(_load("search_page.html"))
        assert hits == [
            MikanSearchHit(
                bangumi_id=3099,
                title="僵尸百分百～在成为僵尸前要做的100件事～",
                poster_path="/images/Bangumi/202307/50f38c71.jpg",
            ),
            MikanSearchHit(
                bangumi_id=1772,
                title="佐贺偶像是传奇",
                poster_path="/images/Bangumi/201810/921ebd34.jpg",
            ),
            MikanSearchHit(
                bangumi_id=4076,
                title="僵尸搜寻中",
                poster_path="/images/Bangumi/202610/25a3140f.jpg",
            ),
            MikanSearchHit(
                bangumi_id=227,
                title="名侦探柯南",
                poster_path="/images/Bangumi/201310/91d95f43.jpg",
            ),
        ]

    def test_page_without_results(self):
        assert parse_mikan_search_page("<html><body></body></html>") == []
        assert parse_mikan_search_page("") == []


@pytest.mark.unit
class TestParseMikanBangumiSubgroups:
    def test_lists_every_subgroup(self):
        subgroups = parse_mikan_bangumi_subgroups(_load("bangumi_page_4076.html"))
        assert subgroups == [
            MikanSubgroup(subgroup_id=1236, name="绿茶字幕组"),
            MikanSubgroup(subgroup_id=615, name="Kirara Fantasia"),
            MikanSubgroup(subgroup_id=202, name="生肉/不明字幕"),
            MikanSubgroup(subgroup_id=534, name="天月动漫&发布组"),
        ]

    def test_joint_group_joins_member_names(self):
        subgroups = parse_mikan_bangumi_subgroups(
            _load("bangumi_page_3141_joint_group.html")
        )
        assert subgroups == [
            MikanSubgroup(subgroup_id=370, name="LoliHouse"),
            MikanSubgroup(subgroup_id=45, name="爱恋字幕社&漫猫字幕组"),
        ]

    def test_page_without_subgroups(self):
        assert parse_mikan_bangumi_subgroups("<html></html>") == []
        assert parse_mikan_bangumi_subgroups("") == []
