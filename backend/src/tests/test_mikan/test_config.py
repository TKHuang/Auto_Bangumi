"""Verify Mikan config section shape."""
import pytest

from module.conf.models import Config, Mikan


@pytest.mark.unit
class TestMikanConfig:
    def test_mikan_defaults(self):
        m = Mikan()
        assert m.base_url == "https://mikanani.me"
        assert m.timeout_seconds == 10
        assert m.max_concurrent == 2
        assert m.min_interval_ms == 500
        assert m.health_ok_window_hours == 1
        assert m.health_down_threshold_hours == 24

    def test_config_includes_mikan_by_default(self):
        c = Config()
        assert isinstance(c.mikan, Mikan)
        assert c.mikan.base_url == "https://mikanani.me"
