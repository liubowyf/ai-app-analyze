from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_frontend_workspace_contains_next_app_entrypoints() -> None:
    assert (REPO_ROOT / "frontend" / "package.json").is_file()
    assert (REPO_ROOT / "frontend" / "app" / "page.tsx").is_file()
