"""Integration tests for CLI functionality."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from gitplex.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI runner."""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def mock_system_checks():
    """Mock system checks."""
    with patch("gitplex.cli.check_system_compatibility") as mock:
        yield mock


def test_cli_setup_and_switch(
    runner: CliRunner,
    temp_workspace: Path,
    mock_system_checks,
) -> None:
    """Test complete CLI workflow with setup and switch."""
    # Setup environment
    os.environ["HOME"] = str(temp_workspace)
    os.environ["GITPLEX_TEST_HOME"] = str(temp_workspace)

    # Create SSH directory
    ssh_dir = temp_workspace / ".ssh"
    ssh_dir.mkdir()

    # Create workspace directory
    workspace_dir = temp_workspace / "personal"
    workspace_dir.mkdir()

    # 1. Setup personal profile
    result = runner.invoke(
        cli,
        [
            "setup",
            "--name",
            "personal",
            "--email",
            "personal@example.com",
            "--username",
            "personal-user",
            "--directory",
            str(workspace_dir),
            "--provider",
            "github",
        ],
    )
    assert result.exit_code == 0, f"Setup failed: {result.output}"
    assert "Profile 'personal' created successfully" in result.output

    # Create second workspace directory
    workspace_dir2 = temp_workspace / "work"
    workspace_dir2.mkdir()

    # 2. Setup work profile
    result = runner.invoke(
        cli,
        [
            "setup",
            "--name",
            "work",
            "--email",
            "work@company.com",
            "--username",
            "work-user",
            "--directory",
            str(workspace_dir2),
            "--provider",
            "gitlab",
        ],
    )
    assert result.exit_code == 0, f"Setup failed: {result.output}"
    assert "Profile 'work' created successfully" in result.output

    # 3. List profiles
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "personal" in result.output
    assert "work" in result.output

    # 4. Switch to work profile
    result = runner.invoke(cli, ["switch", "work"])
    assert result.exit_code == 0
    assert "Switched to profile 'work'" in result.output

    # Verify Git config was updated
    gitconfig = temp_workspace / ".gitconfig"
    assert gitconfig.exists()
    gitconfig_content = gitconfig.read_text()
    assert "work@company.com" in gitconfig_content
    assert "work-user" in gitconfig_content


def test_cli_interactive_setup(
    runner: CliRunner,
    temp_workspace: Path,
    mock_system_checks,
) -> None:
    """Test interactive CLI setup."""
    # Setup environment
    os.environ["HOME"] = str(temp_workspace)
    os.environ["GITPLEX_TEST_HOME"] = str(temp_workspace)

    # Create SSH directory
    ssh_dir = temp_workspace / ".ssh"
    ssh_dir.mkdir()

    # Create workspace directory
    workspace_dir = temp_workspace / "personal"
    workspace_dir.mkdir()

    # Simulate interactive input
    result = runner.invoke(
        cli,
        ["setup"],
        input=(
            f"personal\npersonal@example.com\npersonal-user\n{workspace_dir}\ngithub\n"
        ),
    )

    assert result.exit_code == 0, f"Setup failed: {result.output}"
    assert "Profile 'personal' created successfully" in result.output

    # Verify profile was created
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "personal" in result.output
    assert "personal@example.com" in result.output

    # Verify Git config was created
    gitconfig = temp_workspace / ".gitconfig"
    assert gitconfig.exists()
    assert "personal@example.com" in gitconfig.read_text()


def test_cli_error_handling(
    runner: CliRunner,
    temp_workspace: Path,
    mock_system_checks,
) -> None:
    """Test CLI error handling."""
    # Setup environment
    os.environ["HOME"] = str(temp_workspace)
    os.environ["GITPLEX_TEST_HOME"] = str(temp_workspace)

    # Create SSH directory
    ssh_dir = temp_workspace / ".ssh"
    ssh_dir.mkdir()

    # Try to switch to non-existent profile
    result = runner.invoke(cli, ["switch", "nonexistent"])
    assert result.exit_code == 1
    assert "Profile 'nonexistent' not found" in result.output

    # Create workspace directory
    workspace_dir = temp_workspace / "test"
    workspace_dir.mkdir()

    # Setup a profile
    result = runner.invoke(
        cli,
        [
            "setup",
            "--name",
            "test",
            "--email",
            "test@example.com",
            "--username",
            "test-user",
            "--directory",
            str(workspace_dir),
            "--provider",
            "github",
        ],
    )
    assert result.exit_code == 0

    # Try to create duplicate profile
    result = runner.invoke(
        cli,
        [
            "setup",
            "--name",
            "test",
            "--email",
            "test2@example.com",
            "--username",
            "test-user2",
            "--directory",
            str(temp_workspace / "test2"),
            "--provider",
            "github",
        ],
    )
    assert result.exit_code == 1
    assert "Profile 'test' already exists" in result.output
