from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _load_yaml(relative_path: str) -> dict:
    return yaml.safe_load(_read_text(relative_path))


def test_frontend_dockerfile_exists_and_supports_next_build_runtime():
    dockerfile = ROOT / "frontend" / "Dockerfile"

    assert dockerfile.exists(), "frontend/Dockerfile must exist"

    content = dockerfile.read_text(encoding="utf-8")
    assert "next build" in content or "npm run build" in content
    assert any(command in content for command in ("next start", "npm run start", "server.js"))
    assert "EXPOSE 3000" in content


def test_frontend_and_backend_compose_define_separated_roles():
    frontend_compose = _load_yaml("deploy/frontend/docker-compose.yml")
    backend_compose = _load_yaml("deploy/backend/docker-compose.yml")
    worker_compose = _load_yaml("deploy/worker/docker-compose.yml")

    frontend_services = frontend_compose["services"]
    backend_services = backend_compose["services"]
    worker_services = worker_compose["services"]

    assert "frontend" in frontend_services
    assert set(frontend_services) == {"frontend"}

    frontend_service = frontend_services["frontend"]
    assert frontend_service["build"]
    assert frontend_service["image"] == "apk-analysis/frontend:d889aee"
    assert frontend_service["env_file"]
    assert "NEXT_PUBLIC_API_BASE_URL" in frontend_service["environment"]
    assert any("3000" in str(port) for port in frontend_service["ports"])

    assert set(backend_services) == {"api"}
    api_service = backend_services["api"]
    assert api_service["build"]
    assert api_service["image"].startswith("apk-analysis/backend:")
    assert api_service["env_file"]
    assert "uvicorn api.main:app" in api_service["command"]
    assert api_service["volumes"] == ["${APP_SOURCE_DIR:-/home/devops/ai-app-analyze}:/app:ro"]
    assert api_service["environment"]["APP_SOURCE_DIR"] == "${APP_SOURCE_DIR:-/home/devops/ai-app-analyze}"
    assert any("8000" in str(port) for port in api_service["ports"])

    assert set(worker_services) == {"worker"}
    worker_service = worker_services["worker"]
    assert worker_service["build"]
    assert worker_service["image"].startswith("apk-analysis/backend:")
    assert worker_service["env_file"]
    assert "dramatiq workers.task_actor" in worker_service["command"]
    assert "-l info" not in worker_service["command"]
    assert worker_service["volumes"] == ["${APP_SOURCE_DIR:-/home/devops/ai-app-analyze}:/app:ro"]
    assert worker_service["environment"]["APP_SOURCE_DIR"] == "${APP_SOURCE_DIR:-/home/devops/ai-app-analyze}"
    assert "ports" not in worker_service


def test_backend_image_and_env_examples_define_required_runtime_contract():
    dockerfile = _read_text("Dockerfile.backend")
    backend_env = _read_text("deploy/backend/.env.example")
    worker_env = _read_text("deploy/worker/.env.example")

    assert "apt-get install" in dockerfile
    assert " adb" in dockerfile or "\nadb" in dockerfile
    assert "libglib2.0-0" in dockerfile
    assert "libpango-1.0-0" in dockerfile
    assert "libgdk-pixbuf-2.0-0" in dockerfile
    assert "libcairo2" in dockerfile
    assert "uvicorn api.main:app" not in dockerfile
    assert "dramatiq workers.task_actor" not in dockerfile

    frontend_env = _read_text("deploy/frontend/.env.example")

    assert "NEXT_PUBLIC_API_BASE_URL=" in frontend_env
    assert "PORT=3000" in frontend_env

    for required_name in (
        "APP_SOURCE_DIR=",
        "MYSQL_HOST=",
        "REDIS_BROKER_URL=",
        "MINIO_ENDPOINT=",
        "API_TOKEN=",
        "REDROID_HOST_AGENT_BASE_URL=",
        "REDROID_SLOTS_JSON=",
    ):
        assert required_name in backend_env
        assert required_name in worker_env


def test_docs_cover_local_debug_and_separated_deployment():
    readme = _read_text("README.md")
    current_state = _read_text("docs/CURRENT_STATE.md")
    context_index = _read_text("docs/CONTEXT_INDEX.md")
    combined = "\n".join((readme, current_state, context_index))

    assert "NEXT_PUBLIC_API_BASE_URL" in combined
    assert "docker compose -f deploy/frontend/docker-compose.yml" in combined
    assert "docker compose -f deploy/backend/docker-compose.yml" in combined
    assert "docker compose -f deploy/worker/docker-compose.yml" in combined
    assert "<frontend-node>" in combined
    assert "<api-node>" in combined
    assert "<worker-node>" in combined
    assert "frontend" in combined or "frontend (24)" in combined
    assert "api" in combined or "api (25)" in combined
    assert "worker" in combined or "worker (23)" in combined
    assert "APP_SOURCE_DIR" in combined
    assert "docker compose -f deploy/backend/docker-compose.yml restart api" in combined
    assert "docker compose -f deploy/worker/docker-compose.yml restart worker" in combined
