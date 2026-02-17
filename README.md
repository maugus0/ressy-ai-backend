# RessyAI Backend

FastAPI backend for a multitenant, function-calling voice agent. It streams Twilio audio to Deepgram STS, builds restaurant-specific prompts (menu, specials, FAQs), executes app functions (orders, reservations, FAQs, etc.), and persists calls, transcripts, and orders to MySQL.

## 📋 Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [Environment Configuration](#3-environment-configuration)
  - [Cost Calculation](#4-cost-calculation)
  - [Database Setup](#5-database-setup)
- [Running the Application](#running-the-application)
- [Development Workflow](#development-workflow)
- [Code Quality Standards](#code-quality-standards)
- [Testing](#testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [API Endpoints](#api-endpoints)
- [Architecture](#architecture)
- [Database Migrations](#database-migrations)

## ✨ Features

- **Multitenant Voice Agent**: Routes calls to restaurants based on Twilio phone numbers
- **WebSocket Call Flow**: Real-time audio streaming between Twilio and Deepgram STS
- **Function Calling**: Deepgram Agent FC integration for orders, reservations, FAQs, and SMS Redirect
- **REST APIs**: Comprehensive API for managing restaurants, menus, orders, users, and more
- **MySQL Persistence**: Robust data layer with repository pattern
- **Dynamic Prompts**: Restaurant-specific AI prompts with menu items and FAQs
- **Call Management**: Full call history, transcripts, and analytics

## 📁 Project Structure

```
ressy-ai-backend/
├── app/
│   ├── agent_fc/              # Deepgram function calling framework
│   │   ├── functions/         # Function implementations (orders, reservations, conversation, menu)
│   │   ├── config.py          # Agent FC configuration
│   │   ├── function_definitions.py  # Function definitions
│   │   ├── models.py          # Function call models
│   │   ├── registry.py        # Function registry
│   │   ├── responses.py       # Response models
│   │   ├── router.py          # Function call router
│   │   ├── transport.py       # Transport layer
│   │   └── tests/             # Agent FC tests
│   ├── api/                   # FastAPI route handlers
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── calls.py           # Admin CRM call endpoints
│   │   ├── client_analytics.py  # Client CRM analytics endpoints
│   │   ├── client_calls.py    # Client CRM call endpoints
│   │   ├── client_client_users.py  # Client CRM user management (manager-scoped)
│   │   ├── client_faqs.py     # Client CRM FAQ endpoints
│   │   ├── client_menus.py    # Client CRM menu endpoints
│   │   ├── client_restaurant.py  # Client CRM restaurant endpoints (self-scoped)
│   │   ├── dashboard_orders.py  # Dashboard order management (RBAC)
│   │   ├── dashboard_reservations.py  # Dashboard reservation management (RBAC)
│   │   ├── dashboard_users.py  # Dashboard user management (RBAC)
│   │   ├── faqs.py            # FAQ management endpoints (Admin CRM)
│   │   ├── menus.py           # Menu endpoints (Admin CRM)
│   │   ├── opentable.py       # OpenTable integration endpoints
│   │   ├── order_history.py   # Order history endpoints
│   │   ├── orders.py          # Order endpoints
│   │   ├── reservations.py    # In-house reservation endpoints
│   │   ├── admin_users.py     # Ressy platform admin management endpoints
│   │   ├── client_users.py    # Client CRM user management endpoints (Admin CRM)
│   │   ├── restaurants.py     # Restaurant endpoints (Admin CRM)
│   │   ├── users.py           # User management endpoints
│   │   ├── sse.py             # Server-Sent Events endpoints
│   │   ├── testing.py         # Testing/outbound call endpoints
│   │   └── websocket.py       # WebSocket handler
│   ├── integrations/          # Third-party integrations
│   │   ├── deepgram_client.py
│   │   ├── opentable_client.py
│   │   └── twilio_client.py
│   ├── middleware/            # Request middleware
│   │   └── auth_middleware.py # Authentication and authorization middleware
│   ├── models/                # Data models
│   │   ├── call_models.py     # Call and transcript models
│   │   ├── common_models.py   # Common response models (pagination, etc.)
│   │   ├── menu_models.py     # Menu item models
│   │   └── user_models.py     # User models
│   ├── repositories/          # Data access layer
│   │   ├── mysql_auth_repo.py
│   │   ├── mysql_base.py     # Base MySQL repository
│   │   ├── mysql_call_repo.py
│   │   ├── mysql_faq_repo.py
│   │   ├── mysql_menu_repo.py
│   │   ├── mysql_opentable_log_repo.py
│   │   ├── mysql_order_repo.py
│   │   ├── mysql_reservation_repo.py
│   │   ├── mysql_ressy_admin_repo.py
│   │   ├── mysql_restaurant_admin_repo.py
│   │   ├── mysql_restaurant_repo.py
│   │   ├── mysql_transcript_repo.py
│   │   └── mysql_user_repo.py
│   ├── services/              # Business logic services
│   │   ├── callmanager/       # Call management utilities
│   │   │   ├── call_filler.py
│   │   │   ├── call_latency.py
│   │   │   └── call_state.py
│   │   ├── admin_user_common.py
│   │   ├── auth_service.py
│   │   ├── call_service.py
│   │   ├── client_analytics_service.py
│   │   ├── dashboard_order_service.py
│   │   ├── deepgram_service.py
│   │   ├── faq_service.py
│   │   ├── menu_service.py
│   │   ├── opentable_service.py
│   │   ├── order_service.py
│   │   ├── reservation_service.py
│   │   ├── ressy_admin_service.py
│   │   ├── restaurant_service.py
│   │   ├── restaurant_admin_service.py
│   │   ├── sse_service.py
│   │   ├── transcript_service.py
│   │   ├── twilio_service.py
│   │   ├── user_service.py
│   │   └── websocket_service.py
│   ├── utils/                 # Utility functions
│   │   ├── jwt_util.py        # JWT token utilities
│   │   ├── helpers.py         # Helper functions
│   │   └── prompt_loader.py  # Prompt loading utilities
│   ├── config.py             # Application settings
│   └── main.py               # FastAPI application entry point
├── tests/                     # Test suite
│   ├── conftest.py           # Pytest configuration
│   ├── fake_repos.py         # In-memory test repositories
│   ├── test_api_structure.py # API structure tests
│   ├── test_auth_flows.py    # Authentication flow tests
│   ├── test_config.py        # Configuration tests
│   ├── test_faq_api.py       # FAQ API tests
│   ├── test_faq_service.py   # FAQ service tests
│   ├── test_main.py          # Main app tests
│   ├── test_restaurant_admin_api.py # Client CRM API tests
│   ├── test_restaurant_admin_service.py # Client CRM service tests
│   ├── test_ressy_admin_api.py    # Ressy admin API tests
│   ├── test_ressy_admin_service.py # Ressy admin service tests
│   └── test_syntax.py        # Syntax validation tests
├── migrations/                # Database migration scripts
│   ├── 001_create_permissions.sql through 016_create_*.sql  # Initial schema
│   ├── 017_add_reservation_type_flag.sql through 032_add_24_hours_flag.sql
│   └── README.md             # Migration documentation
├── scripts/                   # Utility scripts
│   ├── add_sample_admins.py  # Add sample admin users
│   ├── add_sample_data.py   # Add sample restaurant data
│   ├── run_migrations.py     # Run database migrations
│   └── seed_pilot_restaurants.py  # Seed pilot restaurants
├── prompts/                   # AI prompt templates
│   └── dg_context_prompt.json
├── .github/
│   └── workflows/
│       └── deploy.yml         # CI/CD pipeline
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── Dockerfile                 # Docker configuration
├── pytest.ini                 # Pytest configuration
├── .flake8                    # Flake8 configuration
├── pyproject.toml             # Tool configurations (Black, isort, mypy, etc.)
├── pre-commit-check.sh        # Pre-commit validation script
└── start.sh                   # Application startup script
```

## 🔧 Prerequisites

- **Python 3.9+** (Python 3.11+ recommended, tested with Python 3.14)
- **MySQL 8.0+** (or compatible database)
- **pip** (Python package manager)
- **OpenSSL** (for generating JWT RSA keys)
- **(Optional) Docker** for containerized deployment

## 🚀 Setup

### 1. Clone the Repository

```bash
git clone https://github.com/maugus0/ressy-ai-backend/
cd ressy-ai-backend
```

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### 3. Environment Configuration

Create a `.env` file in the repository root. The application supports both `DB_*` and `MYSQL_*` prefixes for database configuration.

> ⚠️ **Security**: Never commit real credentials to version control. Use placeholder values in examples. Ensure `.env` is listed in `.gitignore`.

#### 3.1 Database Configuration

**Required (primary):**

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DB_HOST` | string | — | MySQL host |
| `DB_NAME` | string | — | Database name (e.g. `ressy`) |
| `DB_USERNAME` | string | — | MySQL user |
| `DB_PASSWORD` | string | — | MySQL password |
| `DB_PORT` | integer | `3306` | MySQL port |

**Alternative (also supported):** `MYSQL_HOST`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_PORT` — same meaning as `DB_*`; useful for Docker or existing conventions.

**Connection pool (optional):**

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DB_POOL_SIZE` | integer | `10` | Maximum connections in the pool. Increase for high load. |
| `DB_POOL_NAME` | string | `ressy_pool` | Pool identifier for logging |
| `DB_CONNECTION_TIMEOUT` | integer | `20` | Connection timeout in seconds |
| `DB_POOL_LOG_CONNECTIONS` | boolean | `false` | Set to `true` to log connection open/close (debugging) |

#### 3.2 Twilio Configuration (Optional)

Required for voice calls and Twilio webhooks. App can run without them for non-voice features.

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `TWILIO_ACCOUNT_SID` | string | Yes* | `""` | Twilio Account SID for voice and SMS (fallback) |
| `TWILIO_AUTH_TOKEN` | string | Yes* | `""` | Twilio Auth Token for voice and SMS (fallback) |
| `TWILIO_COST_PER_SECOND` | float | No | `0.0003` | Twilio cost per second (USD) for call analytics |
| `TWILIO_MULTIPLIER` | float | No | `1.0` | Multiplier applied to Twilio cost in analytics |
| `NOTIFICATION_MAX_RETRIES` | int | No | `3` | Max retry attempts for failed SMS notifications |

*Required for voice and SMS functionality to work. App runs without them, but voice and SMS features will be disabled.

**SMS Notifications:** When order or reservation status changes, customers automatically receive SMS notifications via Twilio. All messages use a warm, personalized "Ressy" brand voice and end with "Yours sincerely, Ressy AI" signature.

**Credential Priority (Restaurant First, Fallback to .env):**

1. **Primary:** The system first checks the restaurant's `twilio_details` JSON field for `account_sid` and `auth_token`. This is the **preferred configuration** because the "From" number (`twilio_phone_number`) must belong to the Twilio account whose credentials are used—otherwise Twilio returns error 21660 (credential mismatch).

2. **Fallback:** If the restaurant has no `twilio_details` configured, the system falls back to the `.env` variables `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`. In this case, the restaurant's `twilio_phone_number` must belong to the .env Twilio account.

**Restaurant `twilio_details` JSON Format:**
```json
{
  "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "auth_token": "your_auth_token_here"
}
```

**Notification Logging:** All notifications are logged in the `Notification_Logs` table for auditing and retry handling. Failed notifications are marked with `status='failed'` and `retry_count` is incremented. The `get_pending_for_retry()` repository method supports future implementation of a background retry job—no retry worker is included in this release.

**Requirements:** Install the `twilio` package (`pip install -r requirements.txt`).

#### 3.3 Deepgram Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEEPGRAM_API_KEY` | string | — | **Required** for voice/STS features |
| `DEEPGRAM_THINK_PROMPT_FILE` | string | — | Path to think-prompt template (e.g. `prompts/dg_context_prompt.json`) |
| `DEEPGRAM_COST_PER_SECOND` | float | `0.0013333333` | Deepgram cost per second (USD) for call analytics |
| `DEEPGRAM_MULTIPLIER` | float | `1.0` | Multiplier applied to Deepgram cost in analytics |
| `DEEPGRAM_AUDIO_INPUT_ENCODING` | string | `mulaw` | Input audio encoding |
| `DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE` | integer | `8000` | Input sample rate (Hz) |
| `DEEPGRAM_AGENT_LANGUAGE` | string | `en` | Agent language |
| `DEEPGRAM_LISTEN_MODEL` | string | `nova-3` | Listen (ASR) model |
| `DEEPGRAM_THINK_MODEL` | string | `gpt-4o-mini` | Think (LLM) model |
| `DEEPGRAM_SPEAK_MODEL` | string | `aura-2-harmonia-en` | Speak (TTS) model |

#### 3.4 AWS Configuration (Optional)

Used when AWS services are integrated (e.g. region for SDKs).

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AWS_REGION` | string | `ca-central-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | string | — | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | string | — | AWS secret key |

#### 3.5 Outbound Call Configuration (Developer Testing)

Required for the `/api/v1/testing/outbound-call` endpoint. Optional for inbound-only usage.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OUTBOUND_CALL_STATUS_SECRET` | string | — | Secret query param for Twilio status callback; protects `/api/v1/testing/twilio-status` |
| `PUBLIC_BASE_URL` | string | `http://localhost:5001` | Public URL reachable by Twilio (e.g. ngrok URL for streaming and callbacks) |

#### 3.6 Application Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `USE_MOCK_DATA` | boolean | `true` | Use in-memory mocks instead of MySQL when `true` |
| `ALLOW_DB_FAILURE` | boolean | `false` | If `true`, app continues when DB is unavailable (useful for tests) |
| `LOG_LEVEL` | string | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `RESSY_MULTIPLIER` | float | `5.0` | Multiplier for Ressy platform cost in call analytics |
| `RESTAURANT_TIMEZONE` | string | `America/Vancouver` | Default restaurant timezone (IANA) |

#### 3.7 Docker-Specific Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RUN_STARTUP_SCRIPTS` | boolean | `true` | When `true`, runs startup scripts (migrations, seeding). **Preferred** over `SEED_DATABASE`. |
| `SEED_DATABASE` | boolean | `true` | Legacy toggle for seeding; superseded by `RUN_STARTUP_SCRIPTS` when set |
| `DOCKER_MYSQL_PORT` | integer | `3307` | Host port for MySQL container (container internal port remains 3306) |

#### 3.8 JWT Configuration (RS256)

Authentication uses **RS256** with RSA keys (not HS256).

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `JWT_PRIVATE_KEY` | string | — | RSA private key (PEM); escape newlines as `\n` in `.env` |
| `JWT_PUBLIC_KEY` | string | — | RSA public key (PEM); escape newlines as `\n` in `.env` |
| `JWT_ACCESS_TOKEN_EXP_SECONDS` | integer | `3600` | Access token expiry (seconds) |
| `JWT_REFRESH_TOKEN_EXP_SECONDS` | integer | `2592000` | Refresh token expiry (30 days) |
| `JWT_ISSUER` | string | `ressy.ai/auth` | Token issuer |
| `JWT_ADMIN_AUDIENCE` | string | `ressy-admin-api` | Admin API audience |
| `JWT_CLIENT_AUDIENCE` | string | `ressy-client-api` | Client API audience |
| `JWT_AUTH_AUDIENCE` | string | `ressy-auth` | Auth service audience |

**Example `.env` (placeholders only):**

```env
# -------- Database (required) --------
DB_HOST=localhost
DB_NAME=ressy
DB_USERNAME=root
DB_PASSWORD=your_password_here
DB_PORT=3306

MYSQL_HOST=localhost
MYSQL_DATABASE=ressy
MYSQL_USER=root
MYSQL_PASSWORD=your_password_here
MYSQL_PORT=3306

# -------- Database pool (optional) --------
DB_POOL_SIZE=10
DB_POOL_NAME=ressy_pool
DB_CONNECTION_TIMEOUT=20
DB_POOL_LOG_CONNECTIONS=false

# -------- Twilio (optional) --------
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_COST_PER_SECOND=0.0003
TWILIO_MULTIPLIER=1.0

# -------- Deepgram (required for voice) --------
DEEPGRAM_API_KEY=your_deepgram_api_key_here
DEEPGRAM_THINK_PROMPT_FILE=prompts/dg_context_prompt.json
DEEPGRAM_COST_PER_SECOND=0.0013333333
DEEPGRAM_MULTIPLIER=1.0
DEEPGRAM_AUDIO_INPUT_ENCODING=mulaw
DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE=8000
DEEPGRAM_AGENT_LANGUAGE=en
DEEPGRAM_LISTEN_MODEL=nova-3
DEEPGRAM_THINK_MODEL=gpt-4o-mini
DEEPGRAM_SPEAK_MODEL=aura-2-harmonia-en

# -------- AWS (optional) --------
AWS_REGION=ca-central-1
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here

# -------- Outbound call testing (optional) --------
OUTBOUND_CALL_STATUS_SECRET=your_random_secret_string_here
PUBLIC_BASE_URL=https://your-domain.ngrok-free.dev

# -------- Application --------
USE_MOCK_DATA=false
ALLOW_DB_FAILURE=false
LOG_LEVEL=DEBUG
RESSY_MULTIPLIER=5.0
RESTAURANT_TIMEZONE=America/Vancouver

# -------- Docker --------
RUN_STARTUP_SCRIPTS=true
SEED_DATABASE=true
DOCKER_MYSQL_PORT=3307

# -------- JWT (RS256) --------
JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
JWT_ACCESS_TOKEN_EXP_SECONDS=3600
JWT_REFRESH_TOKEN_EXP_SECONDS=2592000
JWT_ISSUER=ressy.ai/auth
JWT_ADMIN_AUDIENCE=ressy-admin-api
JWT_CLIENT_AUDIENCE=ressy-client-api
JWT_AUTH_AUDIENCE=ressy-auth
```

> Store RSA keys as multiline PEM strings; when using a single-line value in `.env`, escape newlines as `\n`.

#### Production JWT setup

1. Generate a 2048-bit RSA keypair (private key stays on auth service only):
   ```bash
   openssl genrsa -out jwt_private.pem 2048
   openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
   ```
2. Configure env vars (example):
   ```env
   JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n<escaped private pem>\n-----END PRIVATE KEY-----"
   JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n<escaped public pem>\n-----END PUBLIC KEY-----"
   JWT_ISSUER=ressy.ai/auth
   JWT_ADMIN_AUDIENCE=ressy-admin-api
   JWT_CLIENT_AUDIENCE=ressy-client-api
   JWT_AUTH_AUDIENCE=ressy-auth
   JWT_ACCESS_TOKEN_EXP_SECONDS=3600
   JWT_REFRESH_TOKEN_EXP_SECONDS=2592000
   ```
3. Deploy the **private key** only to the auth component; deploy the **public key** to any service that validates tokens (if split).
4. Rotate keys via env updates and rolling restarts; ensure both old/new public keys are trusted during rotation if you need overlap.

### 4. Cost Calculation

Call analytics (e.g. Admin CRM call detail `GET /api/v1/admin/calls/{call_id}`) include a cost breakdown:

- **Twilio cost**: `(call duration in seconds) × TWILIO_COST_PER_SECOND × TWILIO_MULTIPLIER`
- **Deepgram cost**: `(call duration in seconds) × DEEPGRAM_COST_PER_SECOND × DEEPGRAM_MULTIPLIER`
- **Ressy cost**: `(Twilio + Deepgram base) × RESSY_MULTIPLIER`

Defaults are set to the highest per-second rates discussed (Twilio ~$0.0003/s, Deepgram ~$0.0013333333/s). Override in `.env` as needed. Cost variables are optional and do not affect voice functionality.

### 5. Database Setup

#### Database Connection Pool Settings

Connection pool behavior is controlled by optional environment variables (see [§ 3.1 Database Configuration](#31-database-configuration)): `DB_POOL_SIZE`, `DB_POOL_NAME`, `DB_CONNECTION_TIMEOUT`, `DB_POOL_LOG_CONNECTIONS`. Defaults are sensible for typical workloads; increase `DB_POOL_SIZE` for high concurrency. These are optional.

#### Run database migrations

```bash
# Using the migration script
python scripts/run_migrations.py

# Or manually using MySQL client
mysql -u root -p ressy < migrations/001_create_permissions.sql
# ... continue for all migration files in order
```

## 🏃 Running the Application

### Development Mode

```bash
# Using the start script
./start.sh

# Or directly with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload
```

The API will be available at `http://localhost:5001`

### Docker Compose (Recommended)

The easiest way to run the entire stack (backend + database) with automatic migrations and seeding:

```bash
# Start everything (build, create database, run migrations, seed data, start app)
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Stop and remove all data (fresh start)
docker-compose down -v
```

**What happens on startup:**
1. MySQL container starts and waits for health check (exposed on port 3307 by default, configurable via `DOCKER_MYSQL_PORT`)
2. Backend container waits for MySQL to be ready
3. Database migrations run automatically (all SQL files in `migrations/`)
4. Startup scripts run if enabled (sample data seeding: admin users, restaurant, menu items, FAQs)
5. Application starts on port 5001

**Default credentials after seeding:**
- **Admin**: `admin@ressy.ai` / `AdminPass!23`
- **Restaurant Manager**: `manager@restaurant.com` / `ManagerPass!23`

**Environment Variables:**

Copy `.env.example` to `.env` and configure (see [§ 3. Environment Configuration](#3-environment-configuration) for full reference). Key variables for Docker:

- **Database**: `DB_PASSWORD` (or `MYSQL_PASSWORD`) — MySQL root password; `DOCKER_MYSQL_PORT` — host port for MySQL (default: `3307`, container uses `3306`).
- **Startup**: `RUN_STARTUP_SCRIPTS` — preferred toggle; when `true`, runs migrations and seeding. `SEED_DATABASE` — legacy toggle; superseded by `RUN_STARTUP_SCRIPTS` when set. Use `RUN_STARTUP_SCRIPTS=false` to skip migrations and seeding.
- **Auth**: `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` — RSA keys (RS256).
- **Voice**: `DEEPGRAM_API_KEY`, `DEEPGRAM_THINK_PROMPT_FILE`, `DEEPGRAM_LISTEN_MODEL`, `DEEPGRAM_THINK_MODEL`, `DEEPGRAM_SPEAK_MODEL`.
- **Outbound testing**: `PUBLIC_BASE_URL` (e.g. ngrok URL), `OUTBOUND_CALL_STATUS_SECRET`.
- **Cost (optional)**: `TWILIO_COST_PER_SECOND`, `DEEPGRAM_COST_PER_SECOND`, `TWILIO_MULTIPLIER`, `DEEPGRAM_MULTIPLIER`, `RESSY_MULTIPLIER`.
- **App**: `LOG_LEVEL`, `RESTAURANT_TIMEZONE`, `USE_MOCK_DATA`, `ALLOW_DB_FAILURE`.

**Disabling startup scripts (preferred over legacy SEED_DATABASE):**

```bash
RUN_STARTUP_SCRIPTS=false docker-compose up --build -d
```

**Legacy: disabling database seeding only:**

```bash
SEED_DATABASE=false docker-compose up --build -d
```

### Docker (Backend Only)

If you have an external MySQL database:

```bash
# Build the Docker image
docker build -t ressy-ai-backend .

# Run the container with environment variables
docker run -p 5001:5001 \
  -e DB_HOST=your-mysql-host \
  -e DB_PORT=3306 \
  -e DB_NAME=ressy \
  -e DB_USERNAME=your-user \
  -e DB_PASSWORD=your-password \
  -e SEED_DATABASE=true \
  ressy-ai-backend
```

### Health Check

```bash
# Check if the API is running
curl http://localhost:5001/health
```

## 👨‍💻 Development Workflow

### Before Committing Code

Always run these commands before committing to ensure code quality:

#### 1. Format Code

```bash
# Format all Python files with Black
black app/ tests/

# Check formatting without making changes
black --check app/ tests/
```

#### 2. Sort Imports

```bash
# Sort imports with isort
isort app/ tests/

# Check import sorting without making changes
isort --check-only app/ tests/
```

#### 3. Lint Code

```bash
# Run flake8 linting
flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203,W503,E501

# Run pylint (code quality)
pylint app/ tests/ --max-line-length=120 --disable=C0111,R0903 || true
```

#### 4. Type Checking

```bash
# Run mypy type checking
mypy app/ --ignore-missing-imports --no-strict-optional || true
```

#### 5. Run Tests

```bash
# Run all tests
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/ -v

# Run tests with coverage
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/ --cov=app --cov-report=html -v

# Run specific test file
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/test_main.py -v
```

#### 6. Security Scan

```bash
# Run Bandit security scan
bandit -r app/ -f json -o bandit-report.json
bandit -r app/
```

### Quick Pre-Commit Checklist

Run this script to check everything at once:

```bash
#!/bin/bash
echo "🔍 Running pre-commit checks..."

echo "1️⃣  Formatting check..."
black --check app/ tests/ || { echo "❌ Formatting failed. Run: black app/ tests/"; exit 1; }

echo "2️⃣  Import sorting check..."
isort --check-only app/ tests/ || { echo "❌ Import sorting failed. Run: isort app/ tests/"; exit 1; }

echo "3️⃣  Linting check..."
flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203,W503,E501 || { echo "❌ Linting failed"; exit 1; }

echo "4️⃣  Running tests..."
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/ -v || { echo "❌ Tests failed"; exit 1; }

echo "✅ All checks passed! Ready to commit."
```

Save this as `pre-commit-check.sh`, make it executable (`chmod +x pre-commit-check.sh`), and run it before committing.

## 📏 Code Quality Standards

### Formatting

- **Line Length**: Maximum 120 characters
- **Formatter**: Black (automatic formatting)
- **Import Sorting**: isort (alphabetical, grouped)

### Linting Rules

- **Tool**: flake8 with custom configuration
- **Ignored Rules**: E203 (whitespace before ':'), W503 (line break before binary operator), E501 (line too long)
- **Style Guide**: PEP 8 compliant

### Type Hints

- Use type hints for function parameters and return types
- Run mypy for type checking (warnings are acceptable, errors should be fixed)

### Code Organization

- Follow the existing project structure
- Keep functions focused and single-purpose
- Use meaningful variable and function names
- Add docstrings for public functions and classes

## 🧪 Testing

### Running Tests

```bash
# Run all tests
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/ -v

# Run with coverage report
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/ --cov=app --cov-report=html --cov-report=xml -v

# Run specific test file
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/test_main.py -v

# Run with detailed output
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/ -v --tb=short
```

### Test Structure

- **test_main.py**: Tests for main FastAPI application and endpoints
- **test_config.py**: Tests for configuration settings
- **test_api_structure.py**: Tests for API structure and imports
- **test_syntax.py**: Syntax validation tests

### Writing Tests

- Place all tests in the `tests/` directory
- Use descriptive test function names starting with `test_`
- Use pytest fixtures from `conftest.py` for common setup
- Mock external dependencies (database, APIs) when possible

## 🔄 CI/CD Pipeline

The project includes a comprehensive CI/CD pipeline that runs on pull requests to `main`. The pipeline includes:

### Pipeline Jobs

1. **Unit Tests**: Runs pytest test suite
2. **Code Formatting**: Checks Black and isort compliance
3. **Linting**: Runs flake8 and pylint
4. **Type Checking**: Runs mypy
5. **Integration Tests**: Runs tests with coverage
6. **Security Audit**: Runs Safety and Bandit
7. **Docker Build**: Builds and validates Docker image
8. **Summary Report**: Generates CI/CD summary

### Running Pipeline Locally

To simulate the CI/CD pipeline locally:

```bash
# 1. Format check
black --check --diff app/ tests/

# 2. Import sorting check
isort --check-only --diff app/ tests/

# 3. Linting
flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203,W503,E501
pylint app/ tests/ --max-line-length=120 --disable=C0111,R0903 || true

# 4. Type checking
mypy app/ --ignore-missing-imports --no-strict-optional || true

# 5. Syntax validation
python -m py_compile app/main.py app/config.py

# 6. Run tests
ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/ -v --tb=short --junitxml=junit-report.xml

# 7. Security scan
safety check --file requirements.txt || true
bandit -r app/ -f json -o bandit-report.json || true

# 8. Docker build (optional)
docker build -t ressy-ai-backend .
```

### Pipeline Configuration

The pipeline configuration is located at `.github/workflows/deploy.yml`. It automatically runs on:
- Pull requests to `main` branch
- Uses Python 3.11
- Sets up all required dependencies
- Generates test reports and artifacts

## 🌐 API Endpoints

### Health & Status

- `GET /` - Root endpoint (health check)
- `GET /health` - Detailed health status

### Twilio Integration

- `POST /voice` - Twilio webhook (returns TwiML `<Stream>`)
- `WS /twilio` - WebSocket endpoint for audio streaming

### REST APIs (prefix: `/api/v1`)

All endpoints are organized by tags in the Swagger documentation:

- **Authentication** (`/auth/*`):
  - `POST /auth/admin/login` - Admin user login
  - `POST /auth/client/login` - Restaurant admin/client login
  - `POST /auth/refresh` - Refresh access token
  - `POST /auth/logout` - Logout and revoke session

- **Users** (`/api/v1/users/*`):
  - `POST /api/v1/users/` - Create user (admin only)
  - `GET /api/v1/users/{restaurant_id}` - List users
  - `PUT /api/v1/users/{user_id}` - Update user
  - `DELETE /api/v1/users/{user_id}` - Delete user

- **Restaurants** (`/api/v1/restaurants/*`) - Admin only:
  - `POST /api/v1/restaurants/` - Create restaurant (validates phone and integration settings)
  - `GET /api/v1/restaurants/` - List restaurants with pagination, search, and credit-card filter
  - `GET /api/v1/restaurants/{id}` - Get restaurant details (includes integration JSON fields and agent capabilities)
  - `PUT /api/v1/restaurants/{id}` - Update restaurant (partial updates supported; includes agent capabilities)
  - `DELETE /api/v1/restaurants/{id}` - Delete restaurant
  - `GET /api/v1/restaurants/{id}/stats` - Aggregated stats (menus, FAQs, admins, calls, minute usage)

- **FAQs** (`/api/v1/admin/*`) - Admin only:
  - `GET /api/v1/admin/restaurants/{restaurant_id}/faqs` - List FAQs for a restaurant
  - `POST /api/v1/admin/restaurants/{restaurant_id}/faqs` - Create FAQ
  - `POST /api/v1/admin/restaurants/{restaurant_id}/faqs/bulk` - Bulk create FAQs
  - `GET /api/v1/admin/faqs/search` - Search FAQs across all restaurants
  - `GET /api/v1/admin/faqs/{faq_id}` - Get FAQ by ID
  - `PUT /api/v1/admin/faqs/{faq_id}` - Update FAQ
  - `DELETE /api/v1/admin/faqs/{faq_id}` - Delete FAQ

- **Menus** (`/api/v1/admin/*`) - Admin only:
  - `POST /api/v1/admin/restaurants/{restaurant_id}/menu` - Create menu item
  - `GET /api/v1/admin/restaurants/{restaurant_id}/menu` - List menu items (paginated, with filters)
  - `GET /api/v1/admin/menu/{menu_id}` - Get menu item by ID
  - `PUT /api/v1/admin/menu/{menu_id}` - Update menu item
  - `DELETE /api/v1/admin/menu/{menu_id}` - Delete menu item
  - `PATCH /api/v1/admin/menu/{menu_id}/availability` - Toggle item availability
  - `PATCH /api/v1/admin/menu/{menu_id}/special` - Toggle special status
  - `PATCH /api/v1/admin/restaurants/{restaurant_id}/menu/bulk-availability` - Bulk update availability
  - `GET /api/v1/admin/restaurants/{restaurant_id}/menu/categories` - Get menu categories

- **Client CRM (scoped, `/api/v1/client/*`)** – restaurant_id is taken from the authenticated restaurant token (`claims["restaurant_id"]`), and user UUID is `claims["sub"]`. **Note**: Sensitive integration details (`twilio_details`, `deepgram_details`, `open_table_details`) are excluded from client endpoints for security:
  - FAQs: `GET/POST /api/v1/client/faqs`, `GET/PUT/DELETE /api/v1/client/faqs/{faq_id}`, `POST /api/v1/client/faqs/bulk`
  - Menus: `GET/POST /api/v1/client/menu`, `GET/PUT/DELETE /api/v1/client/menu/{menu_id}`, `PATCH /api/v1/client/menu/{menu_id}/availability`, `PATCH /api/v1/client/menu/{menu_id}/special`, `PATCH /api/v1/client/menu/bulk-availability`, `GET /api/v1/client/menu/categories`
  - Restaurant self: `GET /api/v1/client/restaurant`, `PUT /api/v1/client/restaurant` (excludes sensitive integration fields; supports agent capabilities including SMS Redirect)
  - Client users (manager role only except self reset): `GET/POST /api/v1/client/users`, `GET/PUT/DELETE /api/v1/client/users/{uuid}`, `POST /api/v1/client/users/{uuid}/reset-password`, `PUT /api/v1/client/users/{uuid}/role`, `POST /api/v1/client/users/bulk`, `POST /api/v1/client/me/reset-password` (self-service)
  - Analytics: `GET /api/v1/client/analytics` - Comprehensive restaurant analytics (calls, reservations, orders, menu, FAQs, customers, recent activity, today's schedule, pending orders), `GET /api/v1/client/analytics/calls` - Detailed call analytics, `GET /api/v1/client/analytics/reservations` - Reservation analytics, `GET /api/v1/client/analytics/orders` - Order analytics, `GET /api/v1/client/analytics/menu` - Menu analytics

- **Orders** (`/api/v1/orders/*`):
  - `POST /api/v1/orders/{restaurant_id}` - Create order
  - `GET /api/v1/orders/{restaurant_id}` - List orders
  - `GET /api/v1/orders/details/{order_id}` - Get order details
  - `PUT /api/v1/orders/{order_id}` - Update order
  - `DELETE /api/v1/orders/{order_id}` - Delete order (admin only)

- **Order History** (`/api/v1/order-history/*`):
  - `GET /api/v1/order-history/{order_id}/history` - Get order history

- **Calls (Admin CRM)** (`/api/v1/admin/calls*`):
  - `GET /api/v1/admin/calls` - Paginated calls across all restaurants with filters/sort
  - `GET /api/v1/admin/calls/{call_id}` - Call detail with transcript and cost breakdown (`twilio_cost`, `deepgram_cost`, `ressy_cost`)
  - `GET /api/v1/admin/calls/analytics` - Aggregated analytics (date range required)
  - `GET /api/v1/admin/calls/search` - Search by caller phone/transcript with filters
  - `DELETE /api/v1/admin/calls/{call_id}` - Delete call (and transcript)
  - `DELETE /api/v1/admin/calls/{call_id}/transcript` - Delete transcript only

- **Outbound Calls (Developer Testing)** (`/api/v1/testing*`):
  - `POST /api/v1/testing/outbound-call` — Place an outbound call to your phone from a restaurant's Twilio number (admin auth required). **Requirements**: `PUBLIC_BASE_URL` (public URL reachable by Twilio, e.g. ngrok) and optionally `OUTBOUND_CALL_STATUS_SECRET` to protect the Twilio status callback. For developer testing only; see [§ 3.5 Outbound Call Configuration](#35-outbound-call-configuration-developer-testing) and Twilio integration.
  - Example cURL (replace `{token}`, `{restaurant_id}`, `{to_number}`):
    ```bash
    curl -X POST "http://localhost:5001/api/v1/testing/outbound-call" \
      -H "Authorization: Bearer {token}" \
      -H "Content-Type: application/json" \
      -d '{"restaurant_id": 1, "to_number": "+15551234567"}'
    ```

- **Calls (Client CRM)** (`/api/v1/client/calls*`) – auto-scoped to authenticated restaurant:
  - `GET /api/v1/client/calls` - Paginated calls with filters/sort
  - `GET /api/v1/client/calls/{call_id}` - Call detail with transcript (ownership enforced)
  - `GET /api/v1/client/calls/analytics` - Restaurant analytics (date range required)
  - `GET /api/v1/client/calls/search` - Search own calls/transcripts
  - `GET /api/v1/client/calls/export` - CSV export with same filters

- **Reservations** (`/api/v1/reservations/*`):
  - `GET /api/v1/reservations/availability/{restaurant_id}` - Get table availability
  - `POST /api/v1/reservations/booking/{restaurant_id}/slot_locks` - Lock booking slot
  - `POST /api/v1/reservations/booking/{restaurant_id}/reservations` - Create reservation
  - `GET /api/v1/reservations/{reservation_id}` - Get reservation details
  - `PUT /api/v1/reservations/{reservation_id}/cancel` - Cancel reservation

- **Dashboard Reservations** (`/api/v1/dashboard/*`) - Requires authentication (admin or client role), RBAC enforced:
  - `POST /api/v1/dashboard/restaurants/{restaurant_id}/reservations` - Create confirmed reservation (Dashboard only)
  - `PUT /api/v1/dashboard/reservations/{reservation_id}/finalize` - Finalize pending reservation
  - `GET /api/v1/dashboard/restaurants/{restaurant_id}/reservations` - Get restaurant reservations with filters
  - `GET /api/v1/dashboard/reservations/{reservation_id}` - Get reservation details
  - `PUT /api/v1/dashboard/reservations/{reservation_id}` - Update reservation
  - `PUT /api/v1/dashboard/reservations/{reservation_id}/cancel` - Cancel reservation

- **Dashboard Orders** (`/api/v1/dashboard/*`) - Requires authentication (admin or client role), RBAC enforced:
  - `POST /api/v1/dashboard/restaurants/{restaurant_id}/orders` - Create order
  - `GET /api/v1/dashboard/restaurants/{restaurant_id}/orders` - Get orders with filters
  - `GET /api/v1/dashboard/orders/{order_id}` - Get order details
  - `PUT /api/v1/dashboard/orders/{order_id}` - Update order
  - `PUT /api/v1/dashboard/orders/{order_id}/status` - Update order status only
  - `PUT /api/v1/dashboard/orders/{order_id}/cancel` - Cancel order
  - `DELETE /api/v1/dashboard/orders/{order_id}` - Soft delete order
  - `PUT /api/v1/dashboard/orders/{order_id}/restore` - Restore deleted order

- **Dashboard Users** (`/api/v1/dashboard/*`) - Requires authentication (admin or client role), RBAC enforced:
  - `POST /api/v1/dashboard/restaurants/{restaurant_id}/users` - Create or add user
  - `GET /api/v1/dashboard/restaurants/{restaurant_id}/users` - Get users with statistics
  - `GET /api/v1/dashboard/users/{user_id}` - Get user details
  - `PUT /api/v1/dashboard/users/{user_id}` - Update user

- **OpenTable** (`/api/v1/opentable/*`):
  - `GET /api/v1/opentable/availability/{restaurant_id}/{rid}` - Get OpenTable availability
  - `POST /api/v1/opentable/booking/{restaurant_id}/{rid}/slot_locks` - Lock OpenTable slot
  - `POST /api/v1/opentable/booking/{restaurant_id}/{rid}/reservations` - Create OpenTable reservation
  - `PUT /api/v1/opentable/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}` - Update reservation
  - `PUT /api/v1/opentable/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}/cancel` - Cancel reservation

- **Ressy Admin Users** (`/api/v1/admin/*`) - Admin only:
  - `POST /api/v1/admin/admin-users` - Create admin user
  - `GET /api/v1/admin/admin-users` - List admin users (with pagination/role filters)
  - `POST /api/v1/admin/admin-users/bulk` - Bulk create admin users (in a transaction)
  - `GET /api/v1/admin/admin-users/{uuid}` - Get admin user by UUID
  - `PUT /api/v1/admin/admin-users/{uuid}` - Update admin user
  - `DELETE /api/v1/admin/admin-users/{uuid}` - Delete admin user
  - `PATCH /api/v1/admin/admin-users/{uuid}/role` - Update role assignment
  - `POST /api/v1/admin/admin-users/{uuid}/reset-password` - Reset password (rate limited, revokes sessions)

- **Client Users** (`/api/v1/admin/*`) - Admin only:
  - `POST /api/v1/admin/restaurants/{restaurant_id}/client-users` - Create client user
  - `GET /api/v1/admin/restaurants/{restaurant_id}/client-users` - List client users for a restaurant
  - `POST /api/v1/admin/restaurants/{restaurant_id}/client-users/bulk` - Bulk create client users (in a transaction)
  - `GET /api/v1/admin/restaurants/{restaurant_id}/client-users/{uuid}` - Get client user by UUID
  - `PUT /api/v1/admin/restaurants/{restaurant_id}/client-users/{uuid}` - Update client user
  - `DELETE /api/v1/admin/restaurants/{restaurant_id}/client-users/{uuid}` - Delete client user
  - `PATCH /api/v1/admin/restaurants/{restaurant_id}/client-users/{uuid}/role` - Update role assignment
  - `POST /api/v1/admin/restaurants/{restaurant_id}/client-users/{uuid}/reset-password` - Reset password (rate limited, revokes sessions)

- **Server-Sent Events (SSE)** (`/api/v1/sse/*`) - Requires authentication (admin or client role), RBAC enforced:
  - `GET /api/v1/sse/events/stream` - Subscribe to real-time event stream (supports header or query param auth)
  - `POST /api/v1/sse/events/escalation/{restaurant_id}` - Trigger escalation event (user_requested, internal_server_error, suspected_spam)
  - `GET /api/v1/sse/events/stats` - Get SSE connection statistics (admin only)

### API Documentation

When running locally, visit:
- Swagger UI: `http://localhost:5001/docs`
- ReDoc: `http://localhost:5001/redoc`

**Security Note**: Client CRM endpoints (`/api/v1/client/*`) exclude sensitive integration details (`twilio_details`, `deepgram_details`, `open_table_details`) from responses. These fields are only accessible through Admin CRM endpoints for security purposes.

### Agent Capabilities

Restaurant `features` control what the voice agent can do for callers. Configure via `PUT /api/v1/restaurants/{id}` (Admin) or `PUT /api/v1/client/restaurant` (Client).

| Capability | Field | Description |
|------------|-------|-------------|
| **Orders (Direct)** | `orders_enabled` | Agent takes pickup orders directly over the phone. Default: `true`. |
| **Reservations (Direct)** | `reservations_enabled` | Agent makes table reservations directly. Default: `true`. |
| **FAQs** | `faqs_enabled` | Agent answers FAQ questions. **Cannot be disabled.** Always `true`. |
| **Orders SMS Redirect** | `orders_sms_redirect` | When enabled, agent sends an SMS with a link to order online instead of taking orders. Requires `orders_enabled=false` and a valid `redirect_url`. |
| **Reservations SMS Redirect** | `reservations_sms_redirect` | When enabled, agent sends an SMS with a link to book online instead of making reservations. Requires `reservations_enabled=false` and a valid `redirect_url`. |

**SMS Redirect configuration:**
```json
{
  "orders_sms_redirect": {
    "enabled": true,
    "redirect_url": "https://order.example.com/restaurant",
    "redirect_message": null
  }
}
```
- `enabled`: Enable SMS redirect for this capability.
- `redirect_url`: **Required when enabled.** Must start with `http://` or `https://`.
- `redirect_message`: Optional custom message template. Use `{redirect_url}` and `{restaurant_name}` as placeholders. Default messages include "RessyAI" signature.

**Business rules:**
- SMS Redirect for orders requires `orders_enabled=false`.
- SMS Redirect for reservations requires `reservations_enabled=false`.
- FAQs cannot be disabled.

### Password Policy

- Admin and client-user passwords must be at least 8 characters and include uppercase, lowercase, and numeric characters.
- Password reset endpoints are rate limited (default 5 attempts per 60-second sliding window per user) and revoke existing refresh sessions.

## 📋 Admin API - cURL Examples

This section contains cURL examples for all Admin API endpoints.

**Base URL**: `http://localhost:5001/api/v1/admin`

**Note**: Replace `{token}` with your actual JWT authentication token obtained from the login endpoint.

### Authentication

#### Admin Login

Login endpoint for Ressy Administrators. Returns JWT token for authenticated admin users.

**Endpoint:** `POST /api/v1/auth/admin/login`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/auth/admin/login' \
--header 'Content-Type: application/json' \
--data '{
    "email": "admin@example.com",
    "password": "your_password"
}'
```

**Request Body:**
- `email` (required): Admin email address
- `password` (required): Admin password

**Response Example:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJlbWFpbCI6ImFkbWluQGV4YW1wbGUuY29tIiwicm9sZSI6ImFkbWluIiwidHlwZSI6ImFkbWluIn0...",
  "token_type": "bearer"
}
```

### Restaurant Management

#### Create Restaurant

Create a new restaurant with all necessary details.

**Endpoint:** `POST /api/v1/restaurants`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/restaurants' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "name": "The Gourmet Restaurant",
    "address": "123 Main Street, City, State 12345",
    "phone_number": "+1-555-123-4567",
    "twilio_phone_number": "+1-555-987-6543",
    "twilio_details": {
        "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "auth_token": "your_auth_token",
        "api_key": "your_api_key"
    },
    "deepgram_details": {
        "api_key": "your_deepgram_api_key",
        "model": "nova-2",
        "language": "en-US"
    },
    "open_table_details": {
        "restaurant_id": "1074796",
        "bearer_token": "your_opentable_token"
    },
    "forward_minutes": 1440,
    "backward_minutes": 0,
    "is_credit_card_required_for_reservation": false
}'
```

**Request Body:**
- `name` (required, string, max 255 chars): Restaurant name
- `address` (optional, text): Restaurant address
- `phone_number` (optional, string, max 20 chars): Phone number
- `twilio_phone_number` (optional, string, max 20 chars): Twilio phone number
- `twilio_details` (optional, JSON object): Twilio configuration
- `deepgram_details` (optional, JSON object): Deepgram configuration
- `open_table_details` (optional, JSON object): OpenTable integration details
- `forward_minutes` (optional, integer, default 0): Forward booking window in minutes
- `backward_minutes` (optional, integer, default 0): Backward booking window in minutes
- `is_credit_card_required_for_reservation` (optional, boolean, default false): Require credit card for reservation
- `features` (optional, object): Agent capabilities—`orders_enabled`, `reservations_enabled`, `faqs_enabled` (cannot disable), and optionally `orders_sms_redirect` / `reservations_sms_redirect` for SMS link redirect. See [Agent Capabilities](#agent-capabilities).

#### Get All Restaurants

Get all restaurants with pagination, search, and filtering.

**Endpoint:** `GET /api/v1/restaurants`

**cURL (With Pagination and Search):**
```bash
curl --location 'http://localhost:5001/api/v1/restaurants?page=1&limit=20&search=Gourmet&is_credit_card_required=false' \
--header 'Authorization: Bearer {token}'
```

**Query Parameters:**
- `page` (optional, default 1, min 1): Page number
- `limit` (optional, default 20, min 1, max 100): Items per page
- `search` (optional): Search by restaurant name (partial match)
- `is_credit_card_required` (optional, boolean): Filter by credit card requirement
- `orders_enabled`, `reservations_enabled`, `faqs_enabled` (optional, boolean): Filter by agent capability flags

#### Get Restaurant by ID

Get complete restaurant details by ID.

**Endpoint:** `GET /api/v1/restaurants/{id}`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/restaurants/1' \
--header 'Authorization: Bearer {token}'
```

#### Update Restaurant

Update restaurant details. Accepts partial updates - only provided fields will be updated.

**Endpoint:** `PUT /api/v1/restaurants/{id}`

**cURL:**
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/restaurants/1' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "name": "The Updated Gourmet Restaurant",
    "forward_minutes": 2880,
    "is_credit_card_required_for_reservation": true
}'
```

#### Delete Restaurant

Delete a restaurant by ID. Cascade deletion will handle associated data automatically.

**Endpoint:** `DELETE /api/v1/restaurants/{id}`

**cURL:**
```bash
curl --location --request DELETE 'http://localhost:5001/api/v1/restaurants/1' \
--header 'Authorization: Bearer {token}'
```

#### Get Restaurant Statistics

Get comprehensive statistics for a restaurant.

**Endpoint:** `GET /api/v1/restaurants/{id}/stats`

**cURL:**
```bash
curl --location 'http://localhost:5001/api/v1/restaurants/1/stats' \
--header 'Authorization: Bearer {token}'
```

**Response Example:**
```json
{
  "total_menu_items": 45,
  "available_menu_items": 42,
  "special_items_count": 5,
  "total_faqs": 12,
  "total_administrators": 3,
  "total_calls": 156,
  "total_minute_usage": 2340.5
}
```

### Admin API Notes

1. **Token Expiration**: JWT tokens expire after 24 hours by default. You'll need to login again to get a new token.
2. **Pagination**: The `limit` parameter has a maximum value of 100. If you need more results, use pagination.
3. **Search**: The search parameter performs a partial match on restaurant names (case-insensitive).
4. **Partial Updates**: The update endpoint accepts partial updates. Only include the fields you want to change.
5. **JSON Fields**: Integration details (`twilio_details`, `deepgram_details`, `open_table_details`) are stored as JSON objects. Ensure proper JSON formatting when sending these fields.
6. **Cascade Deletion**: When deleting a restaurant, associated data (menus, FAQs, orders, etc.) will be automatically deleted due to foreign key constraints.

## 🏗️ Architecture

### Call Flow (Twilio → Deepgram)

1. **Twilio Webhook**: Twilio hits `POST /voice`, which responds with a `<Stream>` that points to `wss://<host>/twilio` and passes `fromNumber`/`toNumber`.

2. **WebSocket Connection**: `app/api/websocket.py` hands the socket to `WebSocketService`.

3. **Service Processing**: The service:
   - Looks up the restaurant by Twilio number, pulls Deepgram API key/keyterms
   - Builds dynamic prompt with menu + FAQs (`prompt_loader.load_think_prompt`)
   - Streams audio to Deepgram STS, forwards agent audio back to Twilio
   - Handles barge-in/clear functionality
   - Routes function calls (orders/reservations/etc.) via `app/agent_fc`
   - Writes transcripts and order data to MySQL

### Key Components

- **WebSocket Service** (`app/services/websocket_service.py`): Manages real-time audio streaming and function calls
- **Deepgram Service** (`app/services/deepgram_service.py`): Handles Deepgram STS connections and prompt building
- **Agent FC** (`app/agent_fc/`): Function calling framework for orders, reservations, conversation, and menu lookups; all agent function calls expect `restaurant_id`
- **Repositories** (`app/repositories/mysql_*.py`): Data access layer for MySQL
- **Services** (`app/services/*.py`): Business logic layer
- **Call Manager** (`app/services/callmanager/`): Call state management and latency tracking
- **Integrations** (`app/integrations/`): Third-party API clients (Deepgram, OpenTable, Twilio)

## 🗄️ Database Migrations

Database migrations are located in the `migrations/` directory and should be run in numerical order:

```bash
# Run migrations using the script
python scripts/run_migrations.py

# Or manually
mysql -u root -p ressy < migrations/001_create_permissions.sql
# Continue for all migration files...
```

### Migration Order

Migrations should be run in numerical order (001, 002, 003, etc.) as they have dependencies on previous tables.

### Migration Files

Run in numerical order (001, 002, … 032). Key migrations:

1. **001_create_permissions.sql** – Permissions table
2. **002_create_crm_roles.sql** – Crm_roles (depends on Permissions)
3. **003_create_users.sql** – Users table
4. **004_create_restaurants.sql** – Restaurants table
5. **005_create_menus.sql** – Menus (depends on Restaurants)
6. **006_create_orders.sql** – Orders (depends on Users)
7. **007_create_order_details.sql** – Order_Details (depends on Orders, Menus)
8. **008_create_faqs.sql** – FAQs (depends on Restaurants)
9. **009_create_notifications.sql** – Notifications (depends on Orders)
10. **010_create_table_availability_requests.sql** – Table_Availability_Requests
11. **011_create_slot_bookings.sql** – Slot_Bookings
12. **012_create_reservations.sql** – Reservations
13. **013_create_ressy_administrator.sql** – Ressy_Administrator
14. **014_create_restaurant_administrators.sql** – Restaurant_Administrators
15. **015_create_calls.sql** – Calls table
16. **016_create_auth_sessions.sql** – Auth_Sessions for JWT refresh
17. **017_add_reservation_type_flag.sql** – Reservation type flag
18. **018_add_restaurant_opening_closing_times.sql** – Restaurant opening/closing times
19. **019_add_party_size_and_special_request.sql** – Party size and special request
20. **020_add_notes_to_reservations.sql** – Notes on reservations
21. **021_add_call_transcript_to_calls.sql** – Call transcript JSON on Calls
22. **022_create_user_restaurant_metadata.sql** – User_Restaurant_Metadata
23. **023_add_restaurant_id_deleted_at_to_orders.sql** – restaurant_id, deleted_at on Orders
24. **024_create_user_activity_history.sql** – User activity history
25. **025_add_unique_phone_number_constraint.sql** – Unique phone constraint
26. **026_add_escalation_forwarding_to_restaurants.sql** – Escalation forwarding
27. **027_create_escalations.sql** – Escalations table
28. **028_add_restaurant_timezone.sql** – Restaurant timezone
29. **029_add_reservation_capacity_config.sql** – Reservation capacity config
30. **030_create_restaurant_features.sql** – Restaurant_Features
31. **031_add_daily_operating_hours.sql** – Per-day operating hours (replaces single opening/closing time)
32. **032_add_24_hours_flag.sql** – Per-day `is_24_hours` flag (when true, open/close times ignored for that day)
33. **033_create_notification_logs.sql** – Notification_Logs
34. **034_alter_notification_logs_columns.sql** – Notification_Logs column updates
35. **035_add_notification_logs_twilio_sid_index.sql** – Twilio SID index
36. **036_recreate_notifications.sql** – Notifications table
37. **037_add_sms_redirect_features.sql** – SMS Redirect fields on Restaurant_Features (orders/reservations redirect URL and message)
38. **038_add_sms_redirect_entity_type.sql** – Add 'sms_redirect' to Notification_Logs entity_type ENUM

**Restaurant operating hours:** Per-day hours (031) support `open`, `close`, `is_closed`, and `is_24_hours` per day. When `is_24_hours` is true for a day, the restaurant is treated as open all day and open/close times are ignored. The voice agent (Deepgram function-calling in `app/agent_fc/`) uses shared utilities (`app.utils.restaurant_hours`: `is_restaurant_open_now`, `is_datetime_within_operating_hours`, `format_operating_window`), which already handle per-day and 24-hour logic—**no agent function code changes are required** for `is_24_hours`.

### Database Schema Overview

#### Core Tables

- **Users**: Customer information
- **Restaurants**: Restaurant details and integrations
- **Menus**: Menu items for restaurants
- **Orders**: Order information
- **Order_Details**: Individual items in orders

#### Reservation System

- **Table_Availability_Requests**: Table availability requests
- **Slot_Bookings**: Available booking slots
- **Reservations**: Confirmed reservations

#### Administrative

- **Permissions**: Route permissions
- **Crm_roles**: Role definitions
- **Ressy_Administrator**: Platform administrators
- **Restaurant_Administrators**: Restaurant-specific administrators

#### Supporting Tables

- **FAQs**: Frequently asked questions
- **Notifications**: Order notifications
- **Calls**: Call session information
- **Auth_Sessions**: JWT refresh token sessions

### Indexes

All tables include appropriate indexes for:

- Primary keys (automatic)
- Foreign keys
- Frequently queried columns
- Composite indexes for common query patterns
- Full-text search indexes where applicable (FAQs)

### Foreign Key Constraints

Foreign keys are set up with appropriate ON DELETE and ON UPDATE actions:

- **CASCADE**: When parent is deleted/updated, child records are deleted/updated
- **RESTRICT**: Prevents deletion/update if child records exist
- **SET NULL**: Sets foreign key to NULL when parent is deleted (where applicable)

### Notes

- All tables use `utf8mb4` character set and `utf8mb4_unicode_ci` collation for full Unicode support
- Timestamps use `TIMESTAMP` type with automatic `created_at` and `updated_at` handling
- JSON columns are used for flexible data storage (order_details, customization, etc.)
- UUIDs are used for administrator tables (VARCHAR(36))

## 📚 Additional Resources

- **CI/CD**: See `.github/workflows/deploy.yml` for pipeline configuration

---

## 🔌 Multitenant WebSocket Implementation

### Overview

The WebSocket handler supports multitenancy, where each incoming call is automatically routed to the correct restaurant based on the Twilio phone number. The system:

1. **Identifies Restaurant**: Extracts Twilio phone number from the call and finds the corresponding restaurant
2. **Loads Context**: Fetches available menu items and FAQs for that restaurant
3. **Dynamic Prompts**: Builds AI prompts with restaurant-specific context
4. **Data Extraction**: Extracts structured data (user details, orders, transcripts) from conversations
5. **Data Storage**: Stores extracted data in MySQL tables

### Architecture

#### Components

1. **WebSocket Service** (`app/services/websocket_service.py`)
   - Handles multitenant call routing
   - Manages conversation history
   - Processes and stores extracted data

2. **Deepgram Service** (`app/services/deepgram_service.py`)
   - Builds dynamic prompts with restaurant context
   - Includes menu items and FAQs in the prompt

3. **MySQL Repositories** (`app/repositories/mysql_*.py`)
   - Restaurant repository: Get restaurant by Twilio number
   - Menu repository: Get available menu items
   - FAQ repository: Get restaurant FAQs
   - User repository: Create/update users
   - Order repository: Create orders and order details
   - Transcript repository: Store call transcripts

### Call Flow

```
1. Call comes in via WebSocket
   ↓
2. Extract Twilio phone number from "start" event
   ↓
3. Query Restaurants table by twilio_phone_number
   ↓
4. Fetch available menu items (is_available = TRUE)
   ↓
5. Fetch FAQs for restaurant
   ↓
6. Build dynamic prompt with menu + FAQs
   ↓
7. Send prompt to Deepgram STS
   ↓
8. Process conversation (collect history)
   ↓
9. On call end: Extract structured data
   ↓
10. Store in MySQL:
    - Users table (user details)
    - Orders table (order info)
    - Order_Details table (order items)
    - Calls table (call metadata and conversation transcript)
```

### Twilio Number Extraction

The system extracts the Twilio phone number from the WebSocket "start" event. The number is typically found in:
- `data["start"]["callSidTo"]` or
- `data["start"]["to"]`

If the number is not found, the system falls back to default configuration.

### Error Handling

- If restaurant not found: Falls back to default prompt
- If menu/FAQs not found: Continues with empty context
- If data extraction fails: Logs error but doesn't crash
- MySQL connection errors: Logged and handled gracefully

---

## 📋 In-House Reservation API Examples

All in-house reservation endpoints are publicly accessible and do not require authentication.

### Base URL
```
http://localhost:5001/api/v1
```

### Public/User APIs

#### 1. Get Table Availability

Get available time slots for a restaurant.

**Endpoint:** `GET /reservations/availability/{restaurant_id}`

**cURL:**
```bash
curl -X GET "http://localhost:5001/api/v1/reservations/availability/1?start_date_time=2024-12-20T18:00:00&forward_minutes=1440&backward_minutes=0&party_size=2" \
  -H "Content-Type: application/json"
```

**Parameters:**
- `restaurant_id` (path): Restaurant ID
- `start_date_time` (query, required): Start date and time in ISO format (e.g., `2024-12-20T18:00:00`)
- `forward_minutes` (query, optional): Forward booking window in minutes (default: restaurant's forward_minutes)
- `backward_minutes` (query, optional): Backward booking window in minutes (default: restaurant's backward_minutes)
- `party_size` (query, optional): Party size

**Response:**
```json
{
  "restaurant_id": 1,
  "start_date_time": "2024-12-20T18:00:00",
  "forward_minutes": 1440,
  "backward_minutes": 0,
  "party_size": 2,
  "slots": [
    {
      "date_time": "2024-12-20T18:00:00",
      "available": true,
      "reservation_token": "abc123..."
    }
  ],
  "total_available": 1
}
```

#### 2. Lock a Booking Slot

Lock a specific time slot for a reservation.

**Endpoint:** `POST /reservations/booking/{restaurant_id}/slot_locks`

**cURL:**
```bash
curl -X POST "http://localhost:5001/api/v1/reservations/booking/1/slot_locks" \
  -H "Content-Type: application/json" \
  -d '{
    "party_size": 2,
    "date_time": "2024-12-20T18:00:00",
    "reservation_attribute": "default"
  }'
```

**Request Body:**
```json
{
  "party_size": 2,
  "date_time": "2024-12-20T18:00:00",
  "reservation_attribute": "default"
}
```

**Response:**
```json
{
  "reservation_token": "550e8400-e29b-41d4-a716-446655440000",
  "date_time": "2024-12-20T18:00:00",
  "party_size": 2,
  "expires_at": "2024-12-20T18:15:00",
  "slot_id": 123
}
```

#### 3. Create Reservation

Create a reservation with pending status.

**Endpoint:** `POST /reservations/booking/{restaurant_id}/reservations`

**cURL:**
```bash
curl -X POST "http://localhost:5001/api/v1/reservations/booking/1/reservations" \
  -H "Content-Type: application/json" \
  -d '{
    "reservation_token": "550e8400-e29b-41d4-a716-446655440000",
    "name": "John Doe",
    "phone_number": "+1234567890",
    "email_address": "john.doe@example.com",
    "special_request": "Window seat preferred"
  }'
```

**Request Body:**
```json
{
  "reservation_token": "550e8400-e29b-41d4-a716-446655440000",
  "name": "John Doe",
  "phone_number": "+1234567890",
  "email_address": "john.doe@example.com",
  "special_request": "Window seat preferred"
}
```

**Note:** Only `name` and `phone_number` are required. `email_address` and `special_request` are optional.

**Response:**
```json
{
  "reservation_id": 456,
  "confirmation_number": "INH-1-A1B2C3D4",
  "status": "pending",
  "date_time": "2024-12-20T18:00:00",
  "message": "Reservation created successfully. Awaiting confirmation from restaurant."
}
```

#### 4. Get Reservation by ID

Get details of a specific reservation.

**Endpoint:** `GET /reservations/{reservation_id}`

**cURL:**
```bash
curl -X GET "http://localhost:5001/api/v1/reservations/456" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "id": 456,
  "reservation_type": "inhouse",
  "table_availability_request_id": null,
  "slot_booking_id": 123,
  "user_id": 789,
  "confirmation_number": "INH-1-A1B2C3D4",
  "last_cancel_time": null,
  "manage_reservation_url": null,
  "status": "pending",
  "created_at": "2024-12-20T17:00:00",
  "updated_at": "2024-12-20T17:00:00",
  "date_time": "2024-12-20T18:00:00",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone_number": "+1234567890"
}
```

#### 5. Cancel Reservation

Cancel a reservation.

**Endpoint:** `PUT /reservations/{reservation_id}/cancel`

**cURL:**
```bash
curl -X PUT "http://localhost:5001/api/v1/reservations/456/cancel" \
  -H "Content-Type: application/json"
```

**Response:**
```json
{
  "reservation_id": 456,
  "status": "cancelled",
  "message": "Reservation cancelled successfully"
}
```

### Dashboard APIs

All dashboard APIs require JWT authentication. They support RBAC:
- **Admins** can access all restaurants' data
- **Restaurant managers/staff** can only access their own restaurant's data

#### 6. Finalize Reservation (Dashboard Only)

Finalize a pending reservation by changing status to confirmed.

**Note**: This endpoint requires JWT authentication (admin or client role).

**Endpoint:** `PUT /api/v1/dashboard/reservations/{reservation_id}/finalize`

**cURL:**
```bash
curl -X PUT "http://localhost:5001/api/v1/dashboard/reservations/456/finalize" \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation_number": "INH-1-A1B2C3D4"
  }'
```

**Request Body (optional):**
```json
{
  "confirmation_number": "INH-1-A1B2C3D4"
}
```

**Response:**
```json
{
  "reservation_id": 456,
  "confirmation_number": "INH-1-A1B2C3D4",
  "status": "confirmed",
  "message": "Reservation confirmed successfully"
}
```

#### 7. Get Reservations by Restaurant (Dashboard)

Get all reservations for a restaurant with filtering options.

**Note**: This endpoint requires JWT authentication (admin or client role). Restaurant managers can only access their own restaurant's reservations.

**Endpoint:** `GET /api/v1/dashboard/restaurants/{restaurant_id}/reservations`

**cURL:**
```bash
curl -X GET "http://localhost:5001/api/v1/dashboard/restaurants/1/reservations?status=pending&start_date=2024-12-20T00:00:00&end_date=2024-12-21T23:59:59&limit=100&offset=0" \
  -H "Content-Type: application/json"
```

**Parameters:**
- `restaurant_id` (path): Restaurant ID
- `status` (query, optional): Filter by status (`pending`, `confirmed`, `cancelled`, `completed`)
- `start_date` (query, optional): Filter by start date (ISO format)
- `end_date` (query, optional): Filter by end date (ISO format)
- `limit` (query, optional): Limit results (default: 100, max: 1000)
- `offset` (query, optional): Offset for pagination (default: 0)

**Response:**
```json
{
  "restaurant_id": 1,
  "reservations": [
    {
      "id": 456,
      "reservation_type": "inhouse",
      "table_availability_request_id": null,
      "slot_booking_id": 123,
      "user_id": 789,
      "confirmation_number": "INH-1-A1B2C3D4",
      "last_cancel_time": null,
      "manage_reservation_url": null,
      "status": "pending",
      "created_at": "2024-12-20T17:00:00",
      "updated_at": "2024-12-20T17:00:00",
      "date_time": "2024-12-20T18:00:00",
      "name": "John Doe",
      "email": "john.doe@example.com",
      "phone_number": "+1234567890"
    }
  ],
  "total": 1
}
```

#### 8. Get Reservation by ID (Dashboard)

Get details of a specific reservation (dashboard version).

**Note**: This endpoint requires JWT authentication (admin or client role).

**Endpoint:** `GET /api/v1/dashboard/reservations/{reservation_id}`

**cURL:**
```bash
curl -X GET "http://localhost:5001/api/v1/dashboard/reservations/456" \
  -H "Content-Type: application/json"
```

#### 9. Cancel Reservation (Dashboard)

Cancel a reservation (dashboard version).

**Note**: This endpoint requires JWT authentication (admin or client role).

**Endpoint:** `PUT /api/v1/dashboard/reservations/{reservation_id}/cancel`

**cURL:**
```bash
curl -X PUT "http://localhost:5001/api/v1/dashboard/reservations/456/cancel" \
  -H "Content-Type: application/json"
```

### Complete Reservation Flow Example

Here's a complete example of the reservation flow:

```bash
# Step 1: Check Availability
curl -X GET "http://localhost:5001/api/v1/reservations/availability/1?start_date_time=2024-12-20T18:00:00&forward_minutes=1440&party_size=2"

# Step 2: Lock a Slot
curl -X POST "http://localhost:5001/api/v1/reservations/booking/1/slot_locks" \
  -H "Content-Type: application/json" \
  -d '{
    "party_size": 2,
    "date_time": "2024-12-20T18:00:00",
    "reservation_attribute": "default"
  }'

# Step 3: Create Reservation
curl -X POST "http://localhost:5001/api/v1/reservations/booking/1/reservations" \
  -H "Content-Type: application/json" \
  -d '{
    "reservation_token": "RESERVATION_TOKEN_FROM_STEP_2",
    "name": "John Doe",
    "phone_number": "+1234567890",
    "email_address": "john.doe@example.com",
    "special_request": "Window seat preferred"
  }'

# Step 4: Finalize Reservation (requires JWT authentication)
curl -X PUT "http://localhost:5001/api/v1/dashboard/reservations/RESERVATION_ID_FROM_STEP_3/finalize" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {your_jwt_token}" \
  -d '{}'
```

### In-House Reservation Notes

1. **Reservation Types**: The system differentiates between `opentable` and `inhouse` reservations using the `reservation_type` flag.

2. **Reservation Status Flow**:
   - `pending` → Created but not yet confirmed
   - `confirmed` → Finalized by restaurant (dashboard only)
   - `cancelled` → Cancelled by user or restaurant
   - `completed` → Reservation completed
   - `no_show` → Customer did not show up

3. **Slot Expiration**: Slots expire after 15 minutes if not used to create a reservation.

4. **Finalization**: Only pending reservations can be finalized. Finalization can only be done through the dashboard API (requires authentication).

5. **Authentication**: Public reservation endpoints (`/api/v1/reservations/*`) are publicly accessible. Dashboard endpoints (`/api/v1/dashboard/*`) require JWT authentication with admin or client role.

6. **Error Responses**: All endpoints may return standard HTTP error responses (400 Bad Request, 404 Not Found, 500 Internal Server Error).

---

### OpenTable API Examples

All OpenTable endpoints require JWT authentication. Include the token in the `Authorization` header.

#### Base URL
```
http://localhost:5001/api/v1/opentable
```

#### Authentication

```bash
# Get JWT token first
curl --location 'http://localhost:5001/api/v1/auth/admin/login' \
--header 'Content-Type: application/json' \
--data '{"email": "admin@ressy.ai", "password": "your_password"}'
```

Then use the token in subsequent requests:
```
Authorization: Bearer {your_jwt_token}
```

#### 1. Get Table Availability

Get available table times for a restaurant.

**Endpoint:** `GET /api/v1/opentable/availability/{restaurant_id}/{rid}`

**cURL:**
```bash
curl --location -g 'http://localhost:5001/api/v1/opentable/availability/1/1074796?start_date_time=2025-03-05T12:00&forward_minutes=60&backward_minutes=30&party_size=2&require_attributes=default&include_credit_card_results=true&include_experiences=false' \
--header 'Authorization: Bearer {token}'
```

**Query Parameters:**
- `start_date_time` (required): Start date and time in format `yyyy-mm-ddThh:ss` (e.g., `2025-03-05T12:00`)
- `forward_minutes` (optional): Forward booking window in minutes
- `backward_minutes` (optional): Backward booking window in minutes
- `party_size` (optional): Party size (must be > 0)
- `require_attributes` (optional): Table types (comma-separated, e.g., `default,window`)
- `include_credit_card_results` (optional): Include credit card results (`true` or `false`)
- `include_experiences` (optional): Include experiences (`true` or `false`)

**Response Example:**
```json
{
  "rid": 1074796,
  "party_size": 2,
  "times": [
    "2025-03-05T07:00",
    "2025-03-05T07:15",
    "2025-03-05T07:30"
  ],
  "times_available": [
    {
      "time": "2025-03-05T07:00",
      "availability_types": [
        {
          "type": "Standard",
          "cancellationPolicy": {},
          "diningArea": [
            {
              "id": 1,
              "attributes": ["default"],
              "environment": "Indoor",
              "booking_url": "https://www.opentable.com/book/validate?...",
              "booking_restref_url": "https://www.opentable.com/restref/client?..."
            }
          ]
        }
      ]
    }
  ],
  "no_availability_reasons": [],
  "href": "https://platform.otqa.com/sync/listings/1074796"
}
```

#### 2. Lock a Booking Slot

Lock a booking slot before creating a reservation.

**Endpoint:** `POST /api/v1/opentable/booking/{restaurant_id}/{rid}/slot_locks`

**cURL (Minimal):**
```bash
curl --location 'http://localhost:5001/api/v1/opentable/booking/1/1074796/slot_locks' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "party_size": 2,
    "date_time": "2025-10-13T16:00",
    "reservation_attribute": "default"
}'
```

**cURL (Full with Experience):**
```bash
curl --location 'http://localhost:5001/api/v1/opentable/booking/1/1074796/slot_locks' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "party_size": 2,
    "date_time": "2025-10-13T16:00",
    "reservation_attribute": "default",
    "experience": {
        "id": 512031,
        "version": 1,
        "party_size_per_price_type": [
            {
                "id": 121058,
                "count": 1
            },
            {
                "id": 121059,
                "count": 1
            }
        ],
        "add_ons": [
            {
                "item_id": "4cb68e46-39be-4110-b345-884bf57635bd",
                "quantity": 2
            }
        ]
    },
    "dining_area_id": 2632,
    "environment": "Indoor"
}'
```

**Request Body:**
- `party_size` (required): Party size (must be > 0)
- `date_time` (required): Date and time in format `yyyy-mm-ddThh:ss`
- `reservation_attribute` (optional, default: "default"): Reservation attribute
- `experience` (optional): Experience details object
- `dining_area_id` (optional): Dining area ID
- `environment` (optional): Environment (e.g., "Indoor", "Outdoor")

**Response Example:**
```json
{
  "expires_at": "2025-01-06T21:24:50",
  "reservation_token": "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiI2MTc3MzgxNDJ8MnwyMDI1LTEwLTEzVDE2OjAwfDEwMzgwMDcifQ.6uVQiE9gzI8nRxIP0qUjP2o__5pwV7DwYeW_0-VPq8oJUvltg-HIj8iel3acYzWeKZuQqLHNiBQ3VlSVeONYGQ"
}
```

#### 3. Create a Reservation

Create a reservation using a reservation token from slot lock.

**Endpoint:** `POST /api/v1/opentable/booking/{restaurant_id}/{rid}/reservations`

**cURL (Minimal):**
```bash
curl --location 'http://localhost:5001/api/v1/opentable/booking/1/1074796/reservations' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "reservation_token": "eyJhbGciOiJIUzUxMiJ9...",
    "first_name": "Jane",
    "last_name": "Doe",
    "email_address": "jane.doe@example.com",
    "phone": {
        "number": "4155555555",
        "country_code": "US",
        "phone_type": "mobile"
    }
}'
```

**cURL (Full with Credit Card and Experience):**
```bash
curl --location 'http://localhost:5001/api/v1/opentable/booking/1/1074796/reservations' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "reservation_token": "eyJhbGciOiJIUzUxMiJ9...",
    "first_name": "Jane",
    "last_name": "Doe",
    "email_address": "JaneDoe@mailanator.com",
    "phone": {
        "number": "4155555555",
        "country_code": "US",
        "phone_type": "mobile"
    },
    "reservation_attribute": "default",
    "special_request": "This is my special request",
    "credit_card": {
        "token": "tok_0SDBnhjrulGLaJAMRTatEB0N",
        "last4": "4242"
    },
    "restaurant_email_marketing_opt_in": "true",
    "dining_area_id": "2632",
    "environment": "Indoor",
    "experience": {
        "id": 512031,
        "version": 1,
        "party_size_per_price_type": [
            {
                "id": 121058,
                "count": 1
            },
            {
                "id": 121059,
                "count": 1
            }
        ],
        "add_ons": [
            {
                "item_id": "4cb68e46-39be-4110-b345-884bf57635bd",
                "quantity": 2
            }
        ]
    }
}'
```

**Request Body:**
- `reservation_token` (required): Token from slot lock
- `first_name` (required): First name (min length: 1)
- `last_name` (required): Last name (min length: 1)
- `email_address` (required): Email address
- `phone` (required): Phone object with `number`, `country_code`, `phone_type`
- `reservation_attribute` (optional, default: "default"): Reservation attribute
- `special_request` (optional): Special request text
- `credit_card` (optional): Credit card object with `token` and `last4`
- `restaurant_email_marketing_opt_in` (optional): Marketing opt-in ("true" or "false")
- `dining_area_id` (optional): Dining area ID
- `environment` (optional): Environment
- `experience` (optional): Experience details object

**Response Example:**
```json
{
  "message": "We have a 5 minute grace period. Please call us if you are running later than 5 minutes after your reservation time.<br /><br />We may contact you about this reservation, so please ensure your email and phone number are up to date.<br /><br />Your table will be reserved for 1 hour 30 minutes for parties of up to 2; 2 hours for parties of up to 4; 2 hours 30 minutes for parties of up to 6; and 3 hours for parties of 7+.",
  "confirmation_number": 1751,
  "offer_confirmation_number": 0,
  "date_time": "2025-10-13T16:00",
  "party_size": 2,
  "notes": "This is my special request",
  "manage_reservation_url": "https://www.opentable.com/book/view?rid=1038007&confnumber=1751&token=01EMM9tRYsZ5LWf59HhG_iCHIzHSs1Spu-9JvrwKx0nzI1"
}
```

#### 4. Update a Reservation

Update an existing reservation.

**Endpoint:** `PUT /api/v1/opentable/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}`

**cURL (Minimal):**
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/opentable/booking/1/1074796/reservations/1751' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}' \
--data '{
    "date_time": "2025-11-13T16:00",
    "special_request": "Window Table"
}'
```

**Path Parameters:**
- `restaurant_id`: Internal restaurant ID
- `rid`: OpenTable restaurant ID
- `confirmation_id`: Confirmation number from the reservation

**Request Body (All fields optional):**
- `party_size` (optional): New party size (must be > 0)
- `date_time` (optional): New date and time in format `yyyy-mm-ddThh:ss`
- `reservation_attribute` (optional): Reservation attribute
- `reservation_token` (optional): Reservation token (required if changing date/time)
- `special_request` (optional): Special request text
- `experience` (optional): Experience details object

**Response Example:**
```json
{
  "message": "We have a 5 minute grace period. Please call us if you are running later than 5 minutes after your reservation time.<br /><br />We may contact you about this reservation, so please ensure your email and phone number are up to date.<br /><br />Your table will be reserved for 1 hour 30 minutes for parties of up to 2; 2 hours for parties of up to 4; 2 hours 30 minutes for parties of up to 6; and 3 hours for parties of 7+.",
  "confirmation_number": 1751,
  "date_time": "2025-11-13T16:00",
  "party_size": 2,
  "notes": "Window Table"
}
```

#### 5. Cancel a Reservation

Cancel an existing reservation.

**Endpoint:** `PUT /api/v1/opentable/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}/cancel`

**cURL:**
```bash
curl --location --request PUT 'http://localhost:5001/api/v1/opentable/booking/1/1074796/reservations/1751/cancel' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer {token}'
```

**Response Example:**
```json
{
  "success": true,
  "message": "Reservation cancelled successfully"
}
```

#### OpenTable Configuration

Ensure the restaurant has OpenTable configuration in the `open_table_details` JSON field:

```json
{
  "base_url": "https://platform.otqa.com/sync",
  "bearer_token": "your_bearer_token"
}
```

#### OpenTable Reservation Flow

1. Get availability → Lock slot → Create reservation
2. To update: Update reservation (may need new slot lock if changing time)
3. To cancel: Cancel reservation

**Notes:**
- Date/Time format: `yyyy-mm-ddThh:ss` (e.g., `2025-03-05T12:00`)
- URL encoding: Ensure proper URL encoding for query parameters (e.g., `%3A` for `:`)
- All endpoints require JWT authentication
- Restaurant configuration must include OpenTable details in the `open_table_details` JSON field

## 🤝 Contributing

1. Create a feature branch from `main` with your task number (for eg. RA-48)
2. Make your changes following the code quality standards
3. Run the pre-commit checks (formatting, linting, tests)
4. Ensure all tests pass
5. Create a pull request

# Quick Start Guide - Running RessyAI Backend

This guide will help you get the RessyAI Backend up and running quickly.

## 📋 Prerequisites Checklist

Before starting, ensure you have:

- ✅ **Python 3.9+** installed (check with `python3 --version`, Python 3.11+ recommended)
- ✅ **MySQL 8.0+** installed and running
- ✅ **pip** installed (comes with Python)
- ✅ **Git** (if cloning the repository)

## 🚀 Step-by-Step Setup

### Step 1: Navigate to Project Directory

```bash
cd /path/to/ressy-ai-backend
```

### Step 2: Set Up Virtual Environment (Recommended)

**Important**: Always use a virtual environment to avoid conflicts with system Python packages.

```bash
# Create a new virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# You should see (venv) in your terminal prompt
# If you see an error about the venv being broken, recreate it:
# rm -rf venv && python3 -m venv venv && source venv/bin/activate
```

**Note**: You need to activate the virtual environment every time you open a new terminal:
```bash
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
# Make sure venv is activated (you should see (venv) in your prompt)
# Install production dependencies
pip3 install -r requirements.txt

# Install development dependencies (optional, but recommended)
pip3 install -r requirements-dev.txt
```

**Troubleshooting**: If you get "externally-managed-environment" error:
- Make sure the virtual environment is activated: `source venv/bin/activate`
- Check that you're using venv's pip: `which pip3` should show `.../venv/bin/pip3`
- If venv is broken (wrong path), recreate it: `rm -rf venv && python3 -m venv venv`

### Step 4: Set Up Environment Variables

Create or update a `.env` file in the project root. See [§ 3. Environment Configuration](#3-environment-configuration) for the full list (40+ variables). Minimum for local run:

```bash
touch .env
```

Edit `.env` with at least:

```env
# Database (REQUIRED unless USE_MOCK_DATA=true)
DB_HOST=localhost
DB_NAME=ressy
DB_USERNAME=root
DB_PASSWORD=your_mysql_password_here
DB_PORT=3306

# JWT (REQUIRED for auth - RS256)
# Generate: openssl genrsa -out jwt_private.pem 2048 && openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
JWT_ACCESS_TOKEN_EXP_SECONDS=3600
JWT_REFRESH_TOKEN_EXP_SECONDS=2592000
JWT_ISSUER=ressy.ai/auth
JWT_ADMIN_AUDIENCE=ressy-admin-api
JWT_CLIENT_AUDIENCE=ressy-client-api
JWT_AUTH_AUDIENCE=ressy-auth

# Deepgram (REQUIRED for voice)
DEEPGRAM_API_KEY=your_deepgram_api_key_here
DEEPGRAM_THINK_PROMPT_FILE=prompts/dg_context_prompt.json

# Application
USE_MOCK_DATA=false
ALLOW_DB_FAILURE=false
LOG_LEVEL=INFO
RESTAURANT_TIMEZONE=America/Vancouver

# Optional: cost calculation (Admin call detail); defaults are fine
# TWILIO_COST_PER_SECOND=0.0003
# DEEPGRAM_COST_PER_SECOND=0.0013333333
# RESSY_MULTIPLIER=5.0

# Optional: outbound call testing (need PUBLIC_BASE_URL reachable by Twilio, e.g. ngrok)
# PUBLIC_BASE_URL=https://your-ngrok.ngrok-free.dev
# OUTBOUND_CALL_STATUS_SECRET=your_random_secret

# Optional: Docker (when using docker-compose)
# RUN_STARTUP_SCRIPTS=true
# DOCKER_MYSQL_PORT=3307

# Optional: database pool (defaults are fine for most cases)
# DB_POOL_SIZE=10
# DB_CONNECTION_TIMEOUT=20

# AWS (if using AWS features)
AWS_REGION=ca-central-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

**Important**: Replace placeholder values with your actual credentials!

### Step 5: Set Up MySQL Database

#### Option A: Using the Migration Script (Recommended)

```bash
# Make sure MySQL is running
# Then run the migration script
python3 scripts/run_migrations.py
```

This script will:
- Create the database if it doesn't exist
- Run all migrations in order
- Set up all required tables

#### Option B: Manual MySQL Setup

```bash
# 1. Connect to MySQL
mysql -u root -p

# 2. Create the database
CREATE DATABASE IF NOT EXISTS ressy;

# 3. Exit MySQL
exit;

# 4. Run migrations (use script for all 032 files, or run each in order)
python3 scripts/run_migrations.py
# Or manually: mysql -u root -p ressy < migrations/001_create_permissions.sql
# ... then 002 through 032 (see migrations/ directory and Database Migrations section)
```

### Step 6: Verify Database Connection

Test if the database connection works:

```bash
# This will attempt to connect and show any errors
python3 -c "from app.repositories.mysql_base import MySQLBaseRepository; repo = MySQLBaseRepository(); print('✅ Database connection successful!')"
```

If you see connection errors, check:
- MySQL is running: `mysql.server status` or `brew services list` (on macOS)
- Database credentials in `.env` are correct
- Database `ressy` exists

### Step 7: Run the Application

#### Option A: Using the Start Script

```bash
# Make the script executable (first time only)
chmod +x start.sh

# Run the application
./start.sh
```

#### Option B: Using uvicorn Directly

```bash
uvicorn app.main:app --host 0.0.0.0 --port 5001 --reload
```

The `--reload` flag enables auto-reload on code changes (useful for development).

### Step 8: Verify the Application is Running

Open your browser or use curl:

```bash
# Check health endpoint
curl http://localhost:5001/health

# Check root endpoint
curl http://localhost:5001/

# Or visit in browser:
# - API: http://localhost:5001
# - Swagger UI: http://localhost:5001/docs
# - ReDoc: http://localhost:5001/redoc
```

You should see:
```json
{
  "status": "healthy",
  "timestamp": 1234567890.123
}
```

## 🐳 Running with Docker (Alternative)

If you prefer Docker:

```bash
# 1. Build the Docker image
docker build -t ressy-ai-backend .

# 2. Run the container
docker run -p 5001:5001 --env-file .env ressy-ai-backend
```

## 🔧 Troubleshooting

### Issue: "Can't connect to MySQL server"

**Solution**:
- Check if MySQL is running: `mysql.server start` (macOS) or `sudo systemctl start mysql` (Linux)
- Verify database credentials in `.env`
- Check if the database exists: `mysql -u root -p -e "SHOW DATABASES;"`

### Issue: "ModuleNotFoundError"

**Solution**:
- Make sure you've installed dependencies: `pip3 install -r requirements.txt`
- Check if you're using the correct Python version: `python3 --version`

### Issue: "Port 5001 already in use"

**Solution**:
- Find and kill the process: `lsof -ti:5001 | xargs kill -9`
- Or use a different port: `uvicorn app.main:app --host 0.0.0.0 --port 5002 --reload`

### Issue: "DEEPGRAM_API_KEY not set" or "JWT private key not set"

**Solution**:
- Add `DEEPGRAM_API_KEY=your_key` to your `.env` file
- Generate and add JWT RSA keys:
  ```bash
  openssl genrsa -out jwt_private.pem 2048
  openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
  # Then add to .env with escaped newlines (\n)
  ```

### Issue: Database connection fails during startup

**Solution**:
- Set `ALLOW_DB_FAILURE=true` in `.env` for testing (not recommended for production)
- Or ensure MySQL is running and credentials are correct
- If using a connection pool, increase `DB_CONNECTION_TIMEOUT` (default 20s) or check `DB_POOL_SIZE`

### Issue: Outbound call testing fails or Twilio status callback returns 403

**Solution**:
- Set `PUBLIC_BASE_URL` to a URL reachable by Twilio (e.g. your ngrok URL)
- Optionally set `OUTBOUND_CALL_STATUS_SECRET` and pass it as the `secret` query param in Twilio StatusCallback URL

### Issue: Too much or too little logging

**Solution**:
- Set `LOG_LEVEL` in `.env` to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` (default: `INFO`)

## ✅ Success Checklist

Once running, you should be able to:

- [ ] Access `http://localhost:5001/health` and get a healthy response
- [ ] Access `http://localhost:5001/docs` and see Swagger UI
- [ ] See the application logs in your terminal
- [ ] No database connection errors in the logs

## 📚 Next Steps

- Explore the API documentation at `http://localhost:5001/docs`
- Check out the README.md for development workflow
- Review the codebase structure in the `app/` directory

## 🆘 Need Help?

- Check the main [README.md](README.md) for detailed documentation
- Review error messages in the terminal output
- Verify all environment variables are set correctly
- Ensure MySQL is running and accessible

## 📖 Error Responses

All API endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "Error message describing what went wrong"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error message describing the server error"
}
```

## 👥 Attribution

Created by RessyAI Team
