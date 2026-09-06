# Validation

Implementation: bdba9de44c07662cc0288e332117508792e93e33
Baseline: 8e04a8dbf8bc733e4aadf5038371f648083fdc0f

- Focused baseline: 177 passed in 3.27s. New behavior journey cases passed before refactor (67 passed). Final focused: 184 passed in 2.83s.
- Core directories (repositories, domain, services, api_contract, scheduler): 1475 passed, 2 skipped, 2 xfailed, 14 warnings in 64.39s.
- Ruff: six existing I001 findings, identical per-file code/message counts on baseline and current. No new findings. git diff --check passes.
- Full combined command was attempted in an isolated backend copy. Collection first required creating its missing config directory. Original and offline attempts stalled after 1513 reported tests at E2E TestPendingReview::test_activate_with_custom_filter. Original process had an HTTPS connection, but offline retry also stalled, so network is not a proven cause. Both stopped; interruption-induced failure is not an application failure result.
- E2E isolated baseline: 142 passed, 1 skipped, 2 failed in 219.84s. Failures: TestAggregateFullFlow::test_refresh_auto_creates and TestIssue1And2And15_YearMissing::test_auto_create_missing_year. Both expect a nonempty auto-created Bangumi list but receive an empty list. Current E2E: identical 142 passed, 1 skipped, same 2 failed in 217.63s. No new failing case.

## Isolation and reproduction

No real backend data/config was copied or modified. Temporary copies exclude data, config, virtualenvs and caches; create config directory before collection. Use the existing backend/.venv/bin/python from each temporary backend directory.

Core command:
`python -m pytest src/tests/test_repositories/ src/tests/test_domain/ src/tests/test_services/ src/tests/test_api_contract/ src/tests/test_scheduler/ -q`

E2E command (separate process):
`python -m pytest src/tests/test_e2e/ -q -o faulthandler_timeout=45`

Only temporary E2E conftest receives this boundary patch. This is not an unmodified full-suite PASS claim. Both baseline and current use identical patch and fixtures:

```python
@pytest.fixture(autouse=True)
def offline_mikan_boundary(monkeypatch):
    from module.mikan.client import MikanClient
    fixtures = MockRequestContent()
    async def episode(self, info_hash):
        return fixtures.get_html("https://mikanani.me/Home/Episode/" + info_hash), 200
    async def image(self, url):
        return fixtures.get_content(url)
    monkeypatch.setattr(MikanClient, "fetch_episode_page", episode)
    monkeypatch.setattr(MikanClient, "fetch_image", image)
```

Logs retained locally:
- `/var/folders/gs/2hhn8bln4ll0z028xf6n_sm00000gn/T/ab-architecture-tests-jskre6p0/`: full-suite-ready.log, offline-suite.log, core-suite.log, e2e-only.log.
- `/var/folders/gs/2hhn8bln4ll0z028xf6n_sm00000gn/T/ab-baseline-e2e-fy94iys_/`: baseline-e2e.log (single test passed), e2e-offline.log (full E2E baseline).

No repository E2E fixture, schema, downloader configuration or deployment changes were made to conceal failures. Combined-suite isolation and baseline E2E failures are outside this approved refactor.
