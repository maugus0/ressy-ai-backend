#!/bin/bash

# Pre-commit check script for RessyAI Backend
# Run this before committing to ensure code quality

set -e  # Exit on any error

echo "🔍 Running pre-commit checks for RessyAI Backend..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print success
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Function to print error
error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to print warning
warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Activate the local virtual environment if available so the tooling commands
# (black, isort, etc.) are reachable even outside an activated shell.
VENV_ACTIVATED=false
# Support common venv folder names: .venv (preferred), venv (legacy), env.
for VENV_DIR in ".venv" "venv" "env"; do
    if [ -d "${VENV_DIR}" ]; then
        if [ -f "${VENV_DIR}/bin/activate" ]; then
            # shellcheck source=/dev/null
            source "${VENV_DIR}/bin/activate"
            VENV_ACTIVATED=true
            break
        elif [ -f "${VENV_DIR}/Scripts/activate" ]; then
            # shellcheck source=/dev/null
            # Windows virtual environments place activate inside Scripts
            source "${VENV_DIR}/Scripts/activate"
            VENV_ACTIVATED=true
            break
        fi
    fi
done

if [ "${VENV_ACTIVATED}" = true ]; then
    success "Using Python virtual environment"
else
    warning "Proceeding without activating .venv (tools must already be on PATH)"
fi

# Determine which Python executable to use (prefer the one from the virtualenv)
PYTHON_CMD="python"
if ! command -v "${PYTHON_CMD}" > /dev/null 2>&1; then
    if command -v python3 > /dev/null 2>&1; then
        PYTHON_CMD="python3"
    else
        error "Python interpreter not found. Install Python or create the .venv environment."
        exit 1
    fi
fi

# 1. Formatting check
echo "1️⃣  Checking code formatting (Black)..."
if black --check app/ tests/ > /dev/null 2>&1; then
    success "Code formatting is correct"
else
    error "Code formatting failed. Run: black app/ tests/"
    exit 1
fi

# 2. Import sorting check
echo ""
echo "2️⃣  Checking import sorting (isort)..."
if isort --check-only app/ tests/ > /dev/null 2>&1; then
    success "Imports are properly sorted"
else
    error "Import sorting failed. Run: isort app/ tests/"
    exit 1
fi

# 3. Linting check
echo ""
echo "3️⃣  Running linting (flake8)..."
if flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203,W503,E501 > /dev/null 2>&1; then
    success "Linting passed"
else
    error "Linting failed. Run: flake8 app/ tests/ --max-line-length=120 --extend-ignore=E203,W503,E501"
    exit 1
fi

# 4. Syntax validation
echo ""
echo "4️⃣  Validating Python syntax..."
if "${PYTHON_CMD}" -m py_compile app/main.py app/config.py > /dev/null 2>&1; then
    success "Syntax validation passed"
else
    error "Syntax validation failed"
    exit 1
fi

# 5. Running tests
echo ""
echo "5️⃣  Running tests..."
if ALLOW_DB_FAILURE=true USE_MOCK_DATA=true pytest tests/ -v --tb=short > /dev/null 2>&1; then
    success "All tests passed"
else
    error "Tests failed. Please run the tests locally and fix the issues."
    exit 1
fi

# 6. Type checking (optional, warnings are acceptable)
echo ""
echo "6️⃣  Running type checking (mypy)..."
if mypy app/ --ignore-missing-imports --no-strict-optional > /dev/null 2>&1; then
    success "Type checking passed"
else
    warning "Type checking completed (warnings are acceptable)"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ All critical checks passed! Ready to commit.${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
