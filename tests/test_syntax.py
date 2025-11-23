"""Syntax validation tests."""

import os
import py_compile


def test_main_syntax():
    """Test that main.py has valid Python syntax."""
    main_path = os.path.join(os.path.dirname(__file__), "..", "app", "main.py")
    py_compile.compile(main_path, doraise=True)


def test_config_syntax():
    """Test that config.py has valid Python syntax."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "app", "config.py")
    py_compile.compile(config_path, doraise=True)


def test_api_files_syntax():
    """Test that API files have valid Python syntax."""
    api_dir = os.path.join(os.path.dirname(__file__), "..", "app", "api")
    api_files = [
        "auth.py",
        "calls.py",
        "admin.py",
        "users.py",
    ]

    for api_file in api_files:
        file_path = os.path.join(api_dir, api_file)
        if os.path.exists(file_path):
            py_compile.compile(file_path, doraise=True)
