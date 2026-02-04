"""
Example tests to verify pytest and pytest-asyncio infrastructure.

These tests verify:
1. Synchronous test execution
2. Asynchronous test execution with pytest-asyncio
"""


def test_example():
    """
    Simple synchronous test to verify pytest is working.
    
    This test should always pass and serves as a sanity check
    that the test infrastructure is properly configured.
    """
    assert 1 + 1 == 2


async def test_async_example():
    """
    Simple asynchronous test to verify pytest-asyncio is working.
    
    This test should always pass and serves as a sanity check
    that async test execution is properly configured.
    """
    assert True
