# RessyAI Backend

FastAPI backend for a multitenant, function-calling voice agent. It streams Twilio audio to Deepgram STS, builds restaurant-specific prompts (menu, specials, FAQs), executes app functions (orders, reservations, FAQs, etc.), and persists calls, transcripts, and orders to MySQL.

## 📋 Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
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
- **Function Calling**: Deepgram Agent FC integration for orders, reservations, and FAQs
- **REST APIs**: Comprehensive API for managing restaurants, menus, orders, users, and more
- **MySQL Persistence**: Robust data layer with repository pattern
- **Dynamic Prompts**: Restaurant-specific AI prompts with menu items and FAQs
- **Call Management**: Full call history, transcripts, and analytics

## 📁 Project Structure

```
ressy-ai-backend/
├── app/
│   ├── agent_fc/              # Deepgram function calling framework
│   │   ├── functions/         # Function implementations (orders, reservations, conversation)
│   │   ├── models.py          # Function call models
│   │   ├── router.py          # Function call router
│   │   └── tests/             # Agent FC tests
│   ├── api/                   # FastAPI route handlers
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── calls.py           # Call management endpoints
│   │   ├── restaurants.py    # Restaurant endpoints
│   │   ├── menus.py           # Menu endpoints
│   │   ├── orders.py          # Order endpoints
│   │   ├── websocket.py       # WebSocket handler
│   │   └── ...                # Other API endpoints
│   ├── config/                # Configuration files
│   ├── core/                  # Core business logic (placeholder)
│   ├── integrations/          # Third-party integrations
│   │   ├── deepgram_client.py
│   │   └── twilio_client.py
│   ├── middleware/            # Request middleware
│   │   └── auth_middleware.py
│   ├── models/                # Data models
│   │   ├── call_models.py
│   │   ├── database.py
│   │   └── user_models.py
│   ├── repositories/          # Data access layer
│   │   ├── mysql_*.py        # MySQL repositories
│   │   └── base.py            # Base repository
│   ├── services/              # Business logic services
│   │   ├── websocket_service.py
│   │   ├── deepgram_service.py
│   │   ├── restaurant_service.py
│   │   └── ...                # Other services
│   ├── utils/                 # Utility functions
│   │   ├── security.py
│   │   ├── helpers.py
│   │   └── prompt_loader.py
│   ├── config.py             # Application settings
│   └── main.py               # FastAPI application entry point
├── tests/                     # Test suite
│   ├── test_main.py          # Main app tests
│   ├── test_config.py        # Configuration tests
│   ├── test_api_structure.py # API structure tests
│   └── test_syntax.py        # Syntax validation tests
├── migrations/                # Database migration scripts
├── scripts/                   # Utility scripts
│   ├── run_migrations.py
│   └── seed_pilot_restaurants.py
├── prompts/                   # AI prompt templates
├── .github/
│   └── workflows/
│       └── deploy.yml         # CI/CD pipeline
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── Dockerfile                 # Docker configuration
├── pytest.ini                 # Pytest configuration
├── .flake8                    # Flake8 configuration
└── pyproject.toml             # Tool configurations (Black, isort, mypy, etc.)
```

## 🔧 Prerequisites

- **Python 3.9+** (Python 3.11 recommended)
- **MySQL 8.0+** (or compatible database)
- **pip** (Python package manager)
- **(Optional) Docker** for containerized deployment

## 🚀 Setup

### 1. Clone the Repository

```bash
git clone https://github.com/maugus0/ressy-ai-backend/
cd ressy-ai-backend
```

### 2. Install Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### 3. Environment Configuration

Create a `.env` file in the repository root:

```env
# Deepgram Configuration
DEEPGRAM_API_KEY=your_deepgram_api_key

# MySQL Database Configuration
DB_HOST=localhost
DB_NAME=ressy
DB_USERNAME=root
DB_PASSWORD=your_password
DB_PORT=3306

# Alternative MySQL environment variables (also supported)
MYSQL_HOST=localhost
MYSQL_DATABASE=ressy
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_PORT=3306

# AWS Configuration (if using DynamoDB)
AWS_REGION=ca-central-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# Application Settings
USE_MOCK_DATA=false
ALLOW_DB_FAILURE=false  # Set to 'true' for testing without database
```

### 4. Database Setup

Run database migrations:

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

### Docker

```bash
# Build the Docker image
docker build -t ressy-ai-backend .

# Run the container
docker run -p 5001:5001 --env-file .env ressy-ai-backend
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

- **Authentication**: `/auth/login`
- **Users**: `/users/*` (CRUD operations)
- **Restaurants**: `/restaurants/*` (CRUD operations)
- **Menus**: `/menu/*` (Menu item management)
- **Specials**: `/specials/*` (Special offers)
- **Orders**: `/orders/*` (Order management)
- **Order History**: `/order-history/*`
- **Transcripts**: `/transcripts/*` (Call transcripts)
- **FAQs**: `/faqs/*` (Frequently asked questions)
- **Calls**: `/calls/*` (Call history and analytics)
- **Admin**: `/admin/*` (Administrative operations)

### API Documentation

When running locally, visit:
- Swagger UI: `http://localhost:5001/docs`
- ReDoc: `http://localhost:5001/redoc`

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
- **Agent FC** (`app/agent_fc/`): Function calling framework for orders, reservations, and conversation
- **Repositories** (`app/repositories/mysql_*.py`): Data access layer for MySQL
- **Services** (`app/services/*.py`): Business logic layer

## 🗄️ Database Migrations

Database migrations are located in the `migrations/` directory and should be run in numerical order:

```bash
# Run migrations using the script
python scripts/run_migrations.py

# Or manually
mysql -u root -p ressy < migrations/001_create_permissions.sql
# Continue for all migration files...
```

See `migrations/README.md` for detailed migration information.

## 📚 Additional Resources

- **Multitenant WebSocket**: See `MULTITENANT_WEBSOCKET.md` for detailed WebSocket implementation
- **Migrations**: See `migrations/README.md` for database schema information
- **CI/CD**: See `.github/workflows/deploy.yml` for pipeline configuration

## 🤝 Contributing

1. Create a feature branch from `main` with your task number (for eg. RA-48)
2. Make your changes following the code quality standards
3. Run the pre-commit checks (formatting, linting, tests)
4. Ensure all tests pass
5. Create a pull request


