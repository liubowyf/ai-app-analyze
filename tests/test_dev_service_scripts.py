from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_dev_up_uses_root_env_and_simple_background_processes():
    content = _read("scripts/dev_up.sh")

    assert 'ENV_FILE="$ROOT_DIR/.env"' in content
    assert 'source "$ENV_FILE"' in content
    assert "nohup" in content
    assert "uvicorn api.main:app" in content
    assert "--workers" not in content
    assert "dramatiq workers.task_actor" in content
    assert "frontend.pid" in content


def test_dev_down_stops_pid_files_and_ports():
    content = _read("scripts/dev_down.sh")

    assert "api.pid" in content
    assert "worker.pid" in content
    assert "frontend.pid" in content
    assert "stop_port 8000" in content
    assert "stop_port 3000" in content


def test_docs_recommend_dev_scripts_for_local_test_env():
    combined = "\n".join(
        (
            _read("README.md"),
            _read("docs/CURRENT_STATE.md"),
            _read("docs/CONTEXT_INDEX.md"),
        )
    )

    assert "./scripts/dev_up.sh" in combined
    assert "./scripts/dev_down.sh" in combined
    assert "./scripts/dev_restart.sh" in combined
    assert ".env" in combined
