import pytest

from loyaltydesk.evals.harness import run_suite


@pytest.mark.asyncio
async def test_golden_suite_passes():
    report = await run_suite()
    assert report["failed"] == 0, report
