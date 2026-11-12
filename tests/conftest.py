import pytest


@pytest.fixture
def anyio_backend():
    # Async tests run on asyncio only (the same event loop uvicorn uses).
    return "asyncio"
