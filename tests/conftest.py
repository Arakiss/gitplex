"""Test configuration and fixtures."""

import os
from pathlib import Path

import pytest


@pytest.fixture
def temp_home(tmp_path: Path) -> Path:
    """Create a temporary home directory for testing."""
    os.environ["GITPLEX_TEST_HOME"] = str(tmp_path)
    yield tmp_path
    del os.environ["GITPLEX_TEST_HOME"]


@pytest.fixture
def mock_system_checks(monkeypatch) -> None:
    """Mock system checks to always pass."""
    def mock_check_git():
        return True, "git version 2.30.1"

    def mock_check_ssh():
        return True

    monkeypatch.setattr("gitplex.system.check_git_installation", mock_check_git)
    monkeypatch.setattr("gitplex.system.check_ssh_agent", mock_check_ssh)


@pytest.fixture
def mock_profile_manager(monkeypatch) -> None:
    """Mock profile manager."""
    pass  # Add mocks if needed
