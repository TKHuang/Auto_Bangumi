"""Rate limiter registry tests (spec §9.2)."""
import pytest

from module.concurrency.registry import (
    get_rate_limiter,
    build_mikan_limiter_from_settings,
)


@pytest.mark.unit
class TestRegistry:
    def setup_method(self):
        # Registry is module-level state; reset between tests.
        from module.concurrency import registry as r
        r._LIMITERS.clear()

    def test_get_same_instance_on_repeated_call(self):
        a = get_rate_limiter("mikan", max_concurrent=2, min_interval_ms=500)
        b = get_rate_limiter("mikan", max_concurrent=999, min_interval_ms=999)
        assert a is b  # subsequent config args ignored once registered

    def test_different_services_have_different_limiters(self):
        a = get_rate_limiter("mikan", max_concurrent=2, min_interval_ms=500)
        b = get_rate_limiter("pikpak", max_concurrent=1, min_interval_ms=1000)
        assert a is not b
        assert a.current_concurrent() == 2
        assert b.current_concurrent() == 1

    def test_build_mikan_limiter_reads_settings(self, monkeypatch):
        from module.conf.models import Mikan
        from module.conf import settings

        mikan_cfg = Mikan(max_concurrent=3, min_interval_ms=750)
        monkeypatch.setattr(settings, "mikan", mikan_cfg, raising=False)

        rl = build_mikan_limiter_from_settings()
        assert rl.current_concurrent() == 3
