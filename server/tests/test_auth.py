import pytest
from httpx import AsyncClient, ASGITransport

from tests.conftest import TEST_API_TOKEN


@pytest.mark.asyncio
async def test_metrics_requires_bearer_token_when_enabled(secure_test_app):
    transport = ASGITransport(app=secure_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/metrics")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_metrics_accepts_valid_bearer_token_when_enabled(secure_test_app):
    transport = ASGITransport(app=secure_test_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {TEST_API_TOKEN}"},
    ) as client:
        resp = await client.get("/api/metrics")
    assert resp.status_code == 200
