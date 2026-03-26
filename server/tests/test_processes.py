# Тесты для API процессов (in-memory хранилище)
import pytest
from httpx import AsyncClient, ASGITransport
from api.processes import update_processes


@pytest.mark.asyncio
async def test_get_processes_returns_list(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/processes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_update_processes_limits_snapshot_size():
    processes = [{"pid": idx, "name": f"proc-{idx}", "cpu": 0.1, "ram": 1.0} for idx in range(2500)]
    update_processes(processes)

    from api.processes import _latest_processes
    assert len(_latest_processes) == 2000
