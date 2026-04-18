"""Smoke tests for new ORM models (spec §6.1)."""
import pytest

from module.domain.models.series import Series
from module.domain.models.mikan_ref import MikanEpisodeRef


@pytest.mark.unit
class TestSeriesModel:
    def test_series_has_required_columns(self):
        cols = {c.name for c in Series.__table__.columns}
        expected = {
            "id", "mikan_bangumi_id", "canonical_title", "normalized_title",
            "season", "cour_part", "year", "root_path", "poster_url",
            "default_filter", "default_offset", "pending_review",
            "created_at", "updated_at", "version",
        }
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_series_unique_constraints(self):
        uq_names = {c.name for c in Series.__table__.constraints
                    if c.__class__.__name__ == "UniqueConstraint"}
        assert "uq_series_mikan" in uq_names
        # uq_series_fallback became a partial Index in migration 0006 (scoped
        # to mikan_bangumi_id IS NULL). It now lives on Series.__table__.indexes,
        # not on .constraints.
        index_names = {ix.name for ix in Series.__table__.indexes}
        assert "uq_series_fallback" in index_names
        assert "uq_series_fallback_null_cour" in index_names


@pytest.mark.unit
class TestMikanEpisodeRefModel:
    def test_required_columns(self):
        cols = {c.name for c in MikanEpisodeRef.__table__.columns}
        expected = {
            "info_hash", "mikan_bangumi_id", "mikan_subgroup_id",
            "canonical_title", "poster_url", "fetched_at",
            "attempt_count", "last_error", "parse_status",
        }
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_info_hash_is_primary_key(self):
        pk_cols = [c.name for c in MikanEpisodeRef.__table__.primary_key.columns]
        assert pk_cols == ["info_hash"]


from module.domain.models.pending_enrichment import PendingTorrentEnrichment


@pytest.mark.unit
class TestPendingTorrentEnrichmentModel:
    def test_required_columns(self):
        cols = {c.name for c in PendingTorrentEnrichment.__table__.columns}
        expected = {
            "info_hash", "raw_name", "homepage", "url", "rss_id",
            "published_at", "first_seen_at", "attempt_count",
            "last_error", "last_attempt_at",
        }
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_rss_id_has_fk(self):
        col = PendingTorrentEnrichment.__table__.c.rss_id
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "rssitem"


from module.domain.models.merge_history import BangumiMergeHistory


@pytest.mark.unit
class TestBangumiMergeHistoryModel:
    def test_required_columns(self):
        cols = {c.name for c in BangumiMergeHistory.__table__.columns}
        expected = {
            "id", "merged_at", "merged_by", "merge_reason",
            "winner_bangumi_id", "loser_bangumi_id",
            "loser_snapshot", "moved_torrent_ids", "dropped_torrents",
            "undone_at", "undone_by",
        }
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_both_bangumi_fks(self):
        winner_col = BangumiMergeHistory.__table__.c.winner_bangumi_id
        loser_col = BangumiMergeHistory.__table__.c.loser_bangumi_id
        assert any(fk.column.table.name == "bangumi" for fk in winner_col.foreign_keys)
        assert any(fk.column.table.name == "bangumi" for fk in loser_col.foreign_keys)
