"""Tests for the Bangumi effective display fields."""

from types import SimpleNamespace

from module.domain.bangumi_view import (
    effective_poster,
    effective_save_path,
    effective_season,
    effective_title,
    effective_year,
)


def _orm(series=None, path_override=None):
    return SimpleNamespace(series=series, path_override=path_override)


def _series(**kw):
    base = dict(
        canonical_title="Frieren",
        season=2,
        year=2023,
        poster_url="posters/f.jpg",
        root_path="/data/Bangumi/Frieren (2023)",
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TestOrmWithSeries:
    def test_fields_read_through_series(self):
        b = _orm(_series())
        assert effective_title(b) == "Frieren"
        assert effective_season(b) == 2
        assert effective_year(b) == 2023
        assert effective_poster(b) == "posters/f.jpg"
        assert effective_save_path(b) == "/data/Bangumi/Frieren (2023)/Season 2"

    def test_path_override_wins(self):
        b = _orm(_series(), path_override="/custom/path")
        assert effective_save_path(b) == "/custom/path"


class TestOrmWithoutSeries:
    def test_defaults(self):
        b = _orm()
        assert effective_title(b) == ""
        assert effective_title(b, default=None) is None
        assert effective_season(b) == 1
        assert effective_year(b) is None
        assert effective_poster(b) is None
        assert effective_save_path(b) is None


class TestFlatDto:
    def test_fields_read_from_dto(self):
        dto = SimpleNamespace(
            official_title="Dto Show",
            season=3,
            year=2024,
            poster_link="posters/d.jpg",
            save_path="/data/Dto/Season 3",
        )
        assert effective_title(dto) == "Dto Show"
        assert effective_season(dto) == 3
        assert effective_year(dto) == 2024
        assert effective_poster(dto) == "posters/d.jpg"
        assert effective_save_path(dto) == "/data/Dto/Season 3"
