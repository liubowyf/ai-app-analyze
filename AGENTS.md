# Repository Guidelines

## Project Structure & Module Organization
Core service code is split by layer:
- `api/`: FastAPI entrypoint (`api/main.py`), routers, and request/response schemas.
- `workers/`: Dramatiq app and async task pipeline (`static`, `dynamic`, `report` queues).
- `modules/`: analysis components (APK parsing, traffic monitoring, AI driver, domain analysis, reporting).
- `core/`: shared config, DB engine/session setup, and storage client wrappers.
- `models/`: SQLAlchemy models and related table definitions.
- `tests/`: unit/integration tests (`test_*.py`).
- `templates/`: report templates (for PDF/report output).
- `docs/`: architecture, operations, and testing references.

## Build, Test, and Development Commands
- `python -m venv venv && source venv/bin/activate`: create and activate local env.
- `pip install -r requirements.txt`: install runtime + test dependencies.
- `uvicorn api.main:app --reload --host 0.0.0.0 --port 8000`: run API locally.
- `dramatiq -A workers.task_actor worker -l info -Q default,static,dynamic,report`: run worker.
- `pytest -v`: run all tests with verbose output.
- `pytest --cov=. --cov-report=html`: run coverage and generate `htmlcov/`.
- `pytest tests/test_tasks_router.py::TestTasksRouter`: run one test class.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and explicit, readable type-friendly Python.
- Keep module/file names snake_case; test files must be `test_<module>.py`.
- Use class names like `Test<Feature>` and test methods like `test_<action>_<expected_result>`.
- Prefer small, focused functions and keep API/router logic thin; business logic belongs in `modules/` or `workers/`.

## Testing Guidelines
- Framework: `pytest` (+ `pytest-asyncio`, `pytest-cov`).
- Reuse fixtures from `tests/conftest.py`; mock external dependencies (DB, storage, network, emulator/AI services).
- Add or update tests for any behavior change before opening a PR.
- Keep coverage from regressing; for critical/new modules, target high coverage (commonly 80%+ in this repo’s plans/docs).

## Commit & Pull Request Guidelines
- Follow Conventional Commit style seen in history: `feat:`, `fix:`, `docs:`, `test:`, `perf:`.
- Keep commits scoped to one change theme.
- PRs should include:
  - clear summary and impacted paths/modules,
  - linked issue/task ID,
  - test evidence (`pytest` command + result),
  - API/report output examples when behavior or format changes.

## Security & Configuration Tips
- Copy `.env.example` to `.env`; never commit secrets.
- Validate key integrations (MySQL/Redis/MinIO/AI endpoint) before running workers.
- Use test doubles/mocks for external systems in CI and local test runs.

## Current Core Baseline (2026-02-22)
- Scope: prioritize end-to-end dynamic analysis core loop only.
- Core loop: `install APK -> launch app -> AI-driven interaction -> network capture -> markdown report`.
- AI interaction core: Open-AutoGLM style single-step agent decision (`do(action=...)` / `finish(...)`) with timeout fallback.
- Exploration strategy:
  - resilient dialog handling + recovery actions,
  - form input + submit retry on login/register pages,
  - navigation + autonomous explore + scenario scripts (`refresh`, `detail_entry`, `return_and_retry`, `relaunch_burst`),
  - runtime budget controls (`APP_EXPLORATION_TIME_BUDGET_SECONDS`, default 540s).
- Network monitoring core:
  - primary pool: strict target-package attribution requests,
  - candidate pool: non-system but lower-confidence requests,
  - both pools must be output separately and in merged evidence view.
- Minimal report output:
  - local screenshots,
  - local `report.md`,
  - sections include coverage checks, action timeline, dynamic domains, DNS/IP clues, master domains, request samples, screenshot index.
- Acceptance targets for current baseline (single run):
  - combined requests `>= 80`,
  - screenshots `>= 10`,
  - dynamic domains `>= 3`,
  - runtime budget target `<= 10 minutes`.

## Persistence & Concurrency Baseline (2026-02-23)
- Core loop has entered productionization baseline (not prototype-only):
  - normalized dynamic persistence is enabled (`dynamic_analysis`, `network_requests`, `master_domains`, `screenshots`),
  - stage run persistence is enabled (`analysis_runs`),
  - distributed emulator lease is enabled (`emulator_leases`, MySQL-backed),
  - distributed proxy-port lease is enabled (`proxy_port_leases`, MySQL-backed),
- task queue is Dramatiq+Redis (`REDIS_BROKER_URL=redis://...`),
  - API evidence query endpoints are enabled (`/tasks/{id}/runs`, `/tasks/{id}/network-requests`, `/tasks/{id}/domains`).
- Parallel execution baseline:
  - with 3 emulator instances, dynamic tasks should run concurrently and bind distinct emulator slots,
  - each dynamic task should bind an isolated mitmproxy port lease to avoid port collisions.

## Deferred For Now
- Keep deferring only non-core expansion work:
  - long-term retention/archiving strategy and cold-storage tiering,
  - schema migration hardening and historical backfill tooling,
  - report format expansion beyond current investigation baseline.
- Priority rule:
  - do not degrade minimal dynamic run quality (`requests/screenshots/domains`) while evolving persistence and distributed execution.
