import fcntl

import pytest

from deployment import init_deployment_role, inspect_primary_lock, release_primary_lock


def test_init_deployment_role_exposes_lock_owner_metadata(tmp_path):
    lock_path = tmp_path / "primary.lock"

    try:
        state = init_deployment_role("primary", "node-a", str(lock_path))
        assert state["role"] == "primary"
        assert state["primary_lock_held"] is True
        assert state["primary_lock_info"]["locked"] is True
        assert state["primary_lock_info"]["owner_node_name"] == "node-a"
    finally:
        release_primary_lock()


def test_init_deployment_role_refuses_locked_primary_path(tmp_path):
    lock_path = tmp_path / "primary.lock"

    with open(lock_path, "a+", encoding="utf-8") as fd:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="Primary lock already held"):
            init_deployment_role("primary", "node-b", str(lock_path))


def test_inspect_primary_lock_reports_unlocked_file_with_metadata(tmp_path):
    lock_path = tmp_path / "primary.lock"
    lock_path.write_text('{"node_name":"node-x","pid":1234,"updated_at":42}', encoding="utf-8")

    info = inspect_primary_lock(str(lock_path))

    assert info["exists"] is True
    assert info["locked"] is False
    assert info["owner_node_name"] == "node-x"
    assert info["owner_pid"] == 1234
