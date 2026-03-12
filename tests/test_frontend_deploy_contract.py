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

    frontend_services = frontend_compose["services"]
    backend_services = backend_compose["services"]

    assert "frontend" in frontend_services
    assert "backend-a" not in frontend_services
    assert "backend-b" not in frontend_services

    frontend_service = frontend_services["frontend"]
    assert frontend_service["build"]
    assert frontend_service["env_file"]
    assert "NEXT_PUBLIC_API_BASE_URL" in frontend_service["environment"]
    assert any("3000" in str(port) for port in frontend_service["ports"])

    assert "backend-a" in backend_services
    assert "backend-b" in backend_services

    for service_name in ("backend-a", "backend-b"):
        service = backend_services[service_name]
        assert service["env_file"]
        assert "uvicorn api.main:app" in service["command"]


def test_deploy_env_examples_define_required_runtime_contract():
    frontend_env = _read_text("deploy/frontend/.env.example")
    backend_env = _read_text("deploy/backend/.env.example")

    assert "NEXT_PUBLIC_API_BASE_URL=" in frontend_env
    assert "PORT=3000" in frontend_env

    for required_name in (
        "MYSQL_HOST=",
        "REDIS_BROKER_URL=",
        "MINIO_ENDPOINT=",
        "API_TOKEN=",
    ):
        assert required_name in backend_env


def test_docs_cover_local_debug_and_separated_deployment():
    readme = _read_text("README.md")
    operations = _read_text("docs/OPERATIONS.md")
    testing_guide = _read_text("docs/TESTING_GUIDE.md")
    combined = "\n".join((readme, operations, testing_guide))

    assert "NEXT_PUBLIC_API_BASE_URL" in combined
    assert "docker compose -f deploy/frontend/docker-compose.yml" in combined
    assert "docker compose -f deploy/backend/docker-compose.yml" in combined
    assert "cd frontend && NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev" in combined
    assert "backend-a" in combined
    assert "backend-b" in combined
