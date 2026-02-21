# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

APK Intelligent Dynamic Analysis Platform - An AI-powered system for automated APK dynamic analysis through simulated user behavior, traffic monitoring, and threat detection.

## Common Development Commands

### Environment Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env
# Edit .env with your configuration
```

### Running Services

```bash
# Start API server (development)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (development - all queues)
celery -A workers.celery_app worker -l info -Q default,static,dynamic,report

# Start Celery worker (production - separate queues)
celery -A workers.celery_app worker -l info -Q static --concurrency=2 --max-tasks-per-child=50
celery -A workers.celery_app worker -l info -Q dynamic --concurrency=4 --max-tasks-per-child=20
celery -A workers.celery_app worker -l info -Q report --concurrency=2 --max-tasks-per-child=100

# API with gunicorn (production)
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_apk_router.py

# Run specific test class
pytest tests/test_apk_router.py::TestAPKUpload

# Run specific test method
pytest tests/test_apk_router.py::TestAPKUpload::test_upload_apk_success

# Run with coverage report
pytest --cov=. --cov-report=html

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```

### Database Operations

```bash
# Initialize database (first time setup)
# Tables are auto-created by FastAPI lifespan in api/main.py on startup
# No separate migration script needed for initial setup

# For schema migrations (if using Alembic)
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Architecture

### System Layers

**API Gateway Layer** (`api/`)
- FastAPI application with REST endpoints
- Routes: `/api/v1/apk/upload`, `/api/v1/tasks`, `/api/v1/whitelist`
- Input validation via Pydantic schemas

**Task Queue Layer** (`workers/`)
- Celery-based async task processing
- Task routing by queue: `static`, `dynamic`, `report`
- Redis as message broker and result backend

**Execution Layer** (`modules/`)
- Functional modules for analysis stages
- Coordinate with external services (emulators, AI)

**Infrastructure Layer**
- MySQL: Task metadata and analysis results
- MinIO: APK files, screenshots, reports
- Redis: Celery broker and result storage
- Android Emulators: Remote device pool (10.16.148.66:5555-5558)
- AI Service: AutoGLM-Phone at 10.16.148.66:6000

### Analysis Pipeline

```
Upload APK → Static Analysis → Dynamic Analysis → Report Generation
                (30s)              (8 min)            (15s)
```

**Task Status Flow**:
`pending` → `queued` → `static_analyzing` → `dynamic_analyzing` → `report_generating` → `completed`

On failure: transition to `failed`, can retry via `/tasks/{id}/retry` endpoint.

### Key Modules

**APK Analyzer** (`modules/apk_analyzer/`)
- Uses androguard for static analysis
- Extracts: package name, permissions, components, signatures

**Android Runner** (`modules/android_runner/`)
- Remote ADB control for emulators
- Methods: `connect_remote_emulator`, `install_apk_remote`, `take_screenshot_remote`, `execute_tap`, `execute_swipe`

**Traffic Monitor** (`modules/traffic_monitor/`)
- mitmproxy-based network interception
- Captures HTTP/HTTPS traffic with whitelist filtering

**AI Driver** (`modules/ai_driver/`)
- AutoGLM-Phone integration for intelligent UI interaction
- Analyzes screenshots and decides next actions

**App Explorer** (`modules/exploration_strategy/`)
- 4-phase exploration strategy:
  1. Basic setup (install, grant permissions, launch)
  2. Navigation exploration (bottom tabs)
  3. Autonomous exploration (AI-driven, max 50 steps)
  4. Scenario testing (search, scroll)

**Screenshot Manager** (`modules/screenshot_manager/`)
- Perceptual hash deduplication (threshold: 10)
- Reduces duplicate screenshots by ~60%

**Domain Analyzer** (`modules/domain_analyzer/`)
- Multi-factor scoring for master domain identification
- Factors: POST/PUT requests, sensitive data, non-standard ports, private IPs, non-HTTPS
- Whitelist filters: CDN, ads, analytics domains

**Report Generator** (`modules/report_generator/`)
- Jinja2 templates + WeasyPrint for PDF generation
- Includes screenshots, network analysis, domain threats

## Important Configuration

### Environment Variables (`.env`)

Critical settings:
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`
- `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` (Celery broker)
- `REDIS_HOST`, `REDIS_PORT` (result backend)
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`
- `AI_BASE_URL`, `AI_MODEL_NAME` (AutoGLM-Phone)
- `ANDROID_EMULATOR_1` through `ANDROID_EMULATOR_4`

**Note**: The code currently uses RabbitMQ as Celery broker but Redis as result backend. Ensure both services are running.

### Database Connection Pool

Configured in `core/database.py`:
- Pool size: 20 base connections
- Max overflow: 10 additional for burst traffic
- Pool recycle: 3600s (1 hour) to prevent MySQL timeout
- SSL enabled with certificate verification disabled

### Celery Configuration

In `workers/celery_app.py`:
- Task timeout: 3600s (1 hour hard limit)
- Soft timeout: 3300s (55 minutes)
- Worker prefetch: 1 task per worker
- Max tasks per child: 50 (recycle worker process)
- Result expires: 86400s (24 hours)

## API Endpoints

### APK Upload
```bash
POST /api/v1/apk/upload
Content-Type: multipart/form-data
File field: file

Returns: task_id, apk_md5, status
```

### Task Management
```bash
POST /api/v1/tasks              # Start analysis (status: pending → queued)
GET  /api/v1/tasks/{task_id}    # Get task status
GET  /api/v1/tasks              # List tasks (paginated)
POST /api/v1/tasks/{task_id}/retry  # Retry failed task
```

### Whitelist Management
```bash
GET    /api/v1/whitelist        # List whitelist rules
POST   /api/v1/whitelist        # Create whitelist rule
PUT    /api/v1/whitelist/{id}   # Update whitelist rule
DELETE /api/v1/whitelist/{id}   # Delete whitelist rule
```

## Emulator Pool Management

Emulator pool defined in `workers/dynamic_analyzer.py`:
```python
EMULATOR_POOL = [
    {"host": "10.16.148.66", "port": 5555, "in_use": False},
    {"host": "10.16.148.66", "port": 5556, "in_use": False},
    {"host": "10.16.148.66", "port": 5557, "in_use": False},
    {"host": "10.16.148.66", "port": 5558, "in_use": False},
]
```

- Simple load balancing: first available emulator
- In-memory `in_use` flag (resets on worker restart)
- Released in `finally` block to ensure cleanup

## Error Handling

### Task Retry Strategy

Tasks defined with `@shared_task(bind=True, max_retries=2)`:
- Max 2 retries for transient errors
- Default retry delay: 300s (5 minutes)
- Manual retry via API endpoint for failed tasks

### Error Classification

- `EmulatorConnectionError`: Switch emulator, retry after 60s
- `APKInstallError`: Mark failed, no retry
- `AIDriverError`: Retry after 300s, max 2 times
- `TrafficMonitorError`: Continue with warning
- `ScreenshotError`: Skip step, continue execution

## Performance Characteristics

- Static analysis: ~30 seconds
- Dynamic analysis: ~8 minutes (50 AI-driven steps)
- Report generation: ~15 seconds
- Total pipeline: ~9 minutes per APK

Screenshot deduplication saves ~60% storage.

## Key Dependencies

- **FastAPI**: Web framework
- **Celery + Redis**: Task queue
- **SQLAlchemy + PyMySQL**: Database ORM
- **MinIO**: Object storage
- **androguard**: APK static analysis
- **mitmproxy**: Traffic interception
- **WeasyPrint**: PDF generation
- **Pillow + imagehash**: Screenshot deduplication
- **OpenAI client**: AI service communication (AutoGLM-Phone)

## Development Workflow

1. Upload APK via `/api/v1/apk/upload` → returns `task_id`
2. Start analysis via `/api/v1/tasks` with `task_id` → task queued
3. Celery worker picks up task, runs static → dynamic → report pipeline
4. Poll `/api/v1/tasks/{task_id}` for status updates
5. Download report when status is `completed`

### Task Flow Sequence

Tasks are automatically chained through Celery:
1. Task created with status `pending`
2. POST `/api/v1/tasks` → status becomes `queued`
3. Celery picks up → `static_analyzing` → `dynamic_analyzing` → `report_generating`
4. Final status: `completed` or `failed`

### Debugging Tips

- Check Celery worker logs: Workers log task progress with task_id
- Database queries: All task data is in MySQL `tasks` table
- MinIO storage: APK files stored in bucket defined by `MINIO_BUCKET`
- Emulator issues: Check `EMULATOR_POOL` in `workers/dynamic_analyzer.py:23-28`
- AI driver errors: Verify `AI_BASE_URL` is accessible and model is loaded

## Documentation

- `README.md`: Project overview and quick start
- `docs/ARCHITECTURE.md`: Detailed system architecture
- `docs/OPERATIONS.md`: Deployment and operations guide
- `docs/TESTING.md`: Testing framework and conventions
- `docs/PRD.md`: Product requirements

## Key Implementation Details

### Celery Task Routing

Tasks are routed to specific queues based on type:
- `workers.static_analyzer.*` → `static` queue
- `workers.dynamic_analyzer.*` → `dynamic` queue
- `workers.report_generator.*` → `report` queue

### Screenshot Deduplication

`modules/screenshot_manager/manager.py` uses perceptual hashing (imagehash):
- Threshold: 10 (hamming distance)
- Saves ~60% storage by filtering duplicate screenshots
- Hash comparison happens before upload to MinIO

### Domain Analysis Scoring

`modules/domain_analyzer/analyzer.py` scores domains on:
- POST/PUT request frequency
- Presence of sensitive data patterns (user_id, device_id, token, etc.)
- Non-standard ports
- Private IP addresses
- Non-HTTPS connections
- Automatically filters CDN, ad, and analytics domains

### AI Integration

AI driver (`modules/ai_driver/`) uses OpenAI client SDK:
- Base URL: `AI_BASE_URL` (default: http://10.16.148.66:6000/v1)
- Model: AutoGLM-Phone-9B
- Analyzes screenshots and decides next UI actions
- Max 50 autonomous exploration steps in Phase 3

### APK Risk Scoring

`modules/apk_analyzer/risk_scorer.py` calculates APK risk scores:

**Risk Factors:**
- Dangerous permissions: +3 points each
- Normal permissions: +1 point each
- Exported components: +2 points each
- No signature: +5 points
- Self-signed: +2 points

**Risk Levels:**
- HIGH: total score >= 20
- MEDIUM: total score >= 10
- LOW: total score < 10

**Caching:**
- LRU cache for APK parsing (max 100 entries)
- Uses MD5 hash as cache key to avoid re-parsing

### Scenario Testing

`modules/scenario_testing/detector.py` detects UI scenarios:

**Supported Scenarios:**
- **Login**: Detects login buttons and credential inputs
- **Payment**: Detects payment buttons, amount inputs, and payment methods
- **Share**: Detects share buttons and social platforms

**Detection Rules:**
- Supports Chinese and English keywords
- Analyzes UI element properties (text, class_name, clickable, editable)
- Pattern matching for common UI patterns

### Exploration Controller

`modules/exploration_strategy/controller.py` manages exploration:

**Depth Control:**
- Max 50 exploration steps
- Prevents infinite exploration loops

**Loop Detection:**
- Tracks screen hashes via MD5
- Detects when same screen appears 3+ times
- Window size: last 10 screens

**Backtracking Strategies:**
- `back`: Go back to previous screen
- `restart`: Restart app from beginning
- `skip`: Skip current exploration path

### Traffic Protocol Support

`modules/traffic_monitor/` supports multiple protocols:

**WebSocket Interceptor:**
- Captures WebSocket messages
- Tracks message direction (send/receive)
- Records payload length and opcode

**gRPC Parser:**
- Detects gRPC requests via content-type header
- Parses gRPC message format (compressed flag + length + payload)
- Extracts method path and message data

## Document Organization

All design and documentation files are in `docs/plans/` directory. See `docs/plans/DOCUMENTATION_INDEX.md` for navigation. Root directory contains only `README.md` and `CLAUDE.md`.
