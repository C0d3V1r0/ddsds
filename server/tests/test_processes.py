# Тесты для API процессов (in-memory хранилище)
import os

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


@pytest.mark.asyncio
async def test_terminate_process_queues_agent_command(test_app, monkeypatch):
    update_processes([{"pid": 4242, "name": "sleep", "cpu": 0.1, "ram": 1024, "start_time": 777}])

    queued: dict[str, object] = {}

    async def fake_send_command(command: str, params: dict, await_result: bool = False, timeout: float = 6.0):
        queued["command"] = command
        queued["params"] = params
        return {"status": "success"}

    monkeypatch.setattr("api.processes.request_agent_command", fake_send_command)
    monkeypatch.setattr("api.processes.get_agent_ws", lambda: object())

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/processes/terminate", json={"pid": 4242})

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert queued["command"] == "kill_process"
    assert queued["params"]["pid"] == 4242
    assert queued["params"]["expected_name"] == "sleep"
    assert queued["params"]["expected_start_time"] == 777
    assert queued["params"]["_meta"]["origin"] == "process_api"
    assert queued["params"]["_meta"]["trace_id"]


@pytest.mark.asyncio
async def test_terminate_process_rejects_protected_process(test_app):
    update_processes([{"pid": 1, "name": "nginx", "cpu": 0.1, "ram": 1024, "start_time": 1}])

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/processes/terminate", json={"pid": 1})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_terminate_process_rejects_current_api_pid(test_app):
    update_processes([{"pid": os.getpid(), "name": "python", "cpu": 0.1, "ram": 1024, "start_time": 1}])

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/processes/terminate", json={"pid": os.getpid()})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_terminate_process_requires_agent_connection(test_app, monkeypatch):
    update_processes([{"pid": 5555, "name": "sleep", "cpu": 0.1, "ram": 1024, "start_time": 777}])
    monkeypatch.setattr("api.processes.get_agent_ws", lambda: None)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/processes/terminate", json={"pid": 5555})

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_force_kill_process_queues_agent_command(test_app, monkeypatch):
    update_processes([{"pid": 9898, "name": "sleep", "cpu": 0.1, "ram": 1024, "start_time": 999}])

    queued: dict[str, object] = {}

    async def fake_send_command(command: str, params: dict, await_result: bool = False, timeout: float = 6.0):
        queued["command"] = command
        queued["params"] = params
        return {"status": "success"}

    monkeypatch.setattr("api.processes.request_agent_command", fake_send_command)
    monkeypatch.setattr("api.processes.get_agent_ws", lambda: object())

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/processes/force-kill", json={"pid": 9898})

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert queued["command"] == "force_kill_process"
    assert queued["params"]["pid"] == 9898
    assert queued["params"]["expected_name"] == "sleep"
    assert queued["params"]["expected_start_time"] == 999
    assert queued["params"]["_meta"]["origin"] == "process_api"
    assert queued["params"]["_meta"]["trace_id"]


@pytest.mark.asyncio
async def test_terminate_process_returns_agent_error(test_app, monkeypatch):
    update_processes([{"pid": 3131, "name": "sleep", "cpu": 0.1, "ram": 1024, "start_time": 111}])

    async def fake_send_command(command: str, params: dict, await_result: bool = False, timeout: float = 6.0):
        return {"status": "error", "error": "permission denied"}

    monkeypatch.setattr("api.processes.request_agent_command", fake_send_command)
    monkeypatch.setattr("api.processes.get_agent_ws", lambda: object())

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/processes/terminate", json={"pid": 3131})

    assert resp.status_code == 502
