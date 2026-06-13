"""Unit tests for `_poster_needs_refresh` — the staleness predicate that gates
the "Refresh Poster" endpoint (`/bangumi/refresh/poster/all`).

A poster is renderable by the WebUI only if it is a present local `posters/*`
cache file or a full `http(s)://` URL. Anything else — empty, or a bare
Mikan-relative `/images/...` path stored when caching failed — must be treated
as stale so the refresh path re-fetches it. The '/images/...' case is the
'躲在超市后门抽烟的两人' regression: the old predicate returned False for it,
so the button silently skipped the broken cover.
"""
from types import SimpleNamespace

from module.api.v1.bangumi import _poster_needs_refresh


def _bangumi(poster):
    return SimpleNamespace(series=SimpleNamespace(poster_url=poster))


def test_none_poster_is_stale():
    assert _poster_needs_refresh(_bangumi(None)) is True


def test_empty_poster_is_stale():
    assert _poster_needs_refresh(_bangumi("")) is True


def test_no_series_is_stale():
    assert _poster_needs_refresh(SimpleNamespace(series=None)) is True


def test_bare_mikan_relative_path_is_stale():
    # The exact value that left '躲在超市后门抽烟的两人' without a cover.
    poster = "/images/Bangumi/202606/1a899936.jpg?width=400&height=560&format=webp"
    assert _poster_needs_refresh(_bangumi(poster)) is True


def test_full_http_url_is_fresh():
    assert _poster_needs_refresh(_bangumi("https://image.tmdb.org/x.jpg")) is False
    assert _poster_needs_refresh(_bangumi("http://example.com/x.jpg")) is False


def test_missing_cached_file_is_stale():
    assert _poster_needs_refresh(_bangumi("posters/does-not-exist-xyz.jpg")) is True


def test_present_cached_file_is_fresh(tmp_path, monkeypatch):
    # `_poster_needs_refresh` checks (Path("data") / poster).exists(); point
    # the relative "data" root at a tmp dir holding the cache file.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "posters").mkdir(parents=True)
    (tmp_path / "data" / "posters" / "present.jpg").write_bytes(b"x")
    assert _poster_needs_refresh(_bangumi("posters/present.jpg")) is False
