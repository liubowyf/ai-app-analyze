from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_start_script_loads_root_env_and_uses_tmux_for_api_and_worker():
    content = _read("scripts/start_services.sh")

    assert 'ENV_FILE="$ROOT_DIR/.env"' in content
    assert "dotenv_values" in content
    assert "load_env_file" in content
    assert "tmux" in content
    assert "intelligent-app-api" in content
    assert "intelligent-app-worker" in content
    assert "intelligent-app-frontend" in content
    assert "uvicorn api.main:app" in content
    assert "dramatiq workers.task_actor" in content
    assert "node \"$standalone_server\"" in content or "node '$standalone_server'" in content


def test_stop_script_terminates_tmux_sessions_and_frontend_pid():
    content = _read("scripts/stop_services.sh")

    assert "tmux has-session -t" in content
    assert "tmux kill-session -t" in content
    assert "pkill -f" in content
    assert "pkill -9 -f" in content
    assert "dramatiq workers.task_actor" in content
    assert "frontend.pid" in content
    assert "intelligent-app-frontend" in content
    assert "stop_port 8000" in content
    assert "stop_port 3000" in content


def test_docs_describe_stable_startup_contract():
    combined = "\n".join(
        (
            _read("README.md"),
            _read("docs/CURRENT_STATE.md"),
            _read("docs/CONTEXT_INDEX.md"),
        )
    )

    assert ".env" in combined
    assert "tmux" in combined
    assert "intelligent-app-api" in combined
    assert "intelligent-app-worker" in combined
    assert "intelligent-app-frontend" in combined
    assert "./scripts/start_services.sh" in combined


def test_frontend_helper_resolves_standalone_server_to_absolute_path():
    content = _read("scripts/run_frontend_service.sh")

    assert 'standalone_server="$(find .next/standalone -type f -path' in content
    assert '$(basename "$standalone_server")' in content


def test_host_agent_image_is_self_contained():
    dockerfile = _read("host_agent/Dockerfile")
    compose = _read("deploy/redroid-host-agent/docker-compose.yml")

    assert "FROM public.ecr.aws/zeek/zeek:lts" in dockerfile
    assert "FROM docker:27-cli AS docker_cli" in dockerfile
    assert "COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker" in dockerfile
    assert "HOST_AGENT_CAPTURE_DIR=/var/lib/redroid-host-agent" in dockerfile
    assert "/opt/zeek" not in dockerfile
    assert "/opt/zeek" not in compose
    assert "/var/run/docker.sock:/var/run/docker.sock" in compose
    assert "/var/lib/redroid-host-agent:/var/lib/redroid-host-agent" in compose
