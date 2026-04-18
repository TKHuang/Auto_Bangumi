import pytest
from module.domain.models.series import Series
from module.repositories.series import SeriesRepository


@pytest.mark.integration
async def test_find_by_canonical_title_returns_undeleted_match(db_session):
    s = Series(
        canonical_title="Demo",
        normalized_title="demo",
        season=1,
        root_path="/p/Demo",
        pending_review=False,
    )
    db_session.add(s)
    await db_session.flush()

    repo = SeriesRepository(db_session)
    found = await repo.find_by_canonical_title("Demo")
    assert found is not None and found.id == s.id

    found_ci = await repo.find_by_canonical_title("demo")
    assert found_ci is not None and found_ci.id == s.id

    miss = await repo.find_by_canonical_title("Other")
    assert miss is None
