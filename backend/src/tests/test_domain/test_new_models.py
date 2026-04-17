"""Smoke tests for new ORM models (spec §6.1)."""
import pytest

from module.domain.models.series import Series


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
        assert "uq_series_fallback" in uq_names
