"""Test CLI functionality."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from gitplex.cli import cli
from gitplex.exceptions import ProfileError
from gitplex.profile import GitProvider, Profile


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_home(tmp_path: Path) -> Generator[Path, None, None]:
    """Create temporary home directory."""
    with patch.dict("os.environ", {"GITPLEX_TEST_HOME": str(tmp_path)}):
        yield tmp_path


@pytest.fixture
def mock_system_checks() -> Generator[Mock, None, None]:
    """Mock system compatibility checks."""
    with patch("gitplex.cli.check_system_compatibility") as mock:
        mock.return_value = None  # Ensure successful check
        yield mock


@pytest.fixture
def mock_profile_manager() -> Generator[Mock, None, None]:
    """Mock profile manager."""
    with patch("gitplex.cli.ProfileManager") as mock:
        yield mock.return_value


@pytest.fixture
def mock_home_dir(temp_home: Path) -> Generator[Mock, None, None]:
    """Mock home directory."""
    with patch("gitplex.cli.get_home_dir") as mock:
        mock.return_value = str(temp_home)
        yield mock


def test_setup_interactive(
    runner: CliRunner,
    mock_system_checks: Mock,
    mock_profile_manager: Mock,
    mock_home_dir: Mock,
    temp_home: Path,
) -> None:
    """Test interactive profile setup."""
    # Create test directory
    test_dir = temp_home / "test_dir"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Mock successful profile creation
    profile = Profile(
        name="test",
        email="test@example.com",
        username="testuser",
        directories=[test_dir],
        providers=[GitProvider("github")],
    )
    mock_profile_manager.setup_profile.return_value = profile

    # Execute
    result = runner.invoke(
        cli,
        ["setup"],
        input=f"test\ntest@example.com\ntestuser\n{test_dir}\ngithub\n",
    )

    # Verify
    assert result.exit_code == 0
    assert "Profile 'test' created successfully" in result.output


def test_setup_non_interactive(
    runner: CliRunner,
    mock_system_checks: Mock,
    mock_profile_manager: Mock,
    mock_home_dir: Mock,
    temp_home: Path,
) -> None:
    """Test non-interactive profile setup."""
    # Create test directory
    test_dir = temp_home / "test_dir"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Mock successful profile creation
    profile = Profile(
        name="test",
        email="test@example.com",
        username="testuser",
        directories=[test_dir],
        providers=[GitProvider("github")],
    )
    mock_profile_manager.setup_profile.return_value = profile

    # Execute
    result = runner.invoke(
        cli,
        [
            "setup",
            "--name", "test",
            "--email", "test@example.com",
            "--username", "testuser",
            "--directory", str(test_dir),
            "--provider", "github",
        ],
    )

    # Verify
    assert result.exit_code == 0
    assert "Profile 'test' created successfully" in result.output


def test_setup_error(
    runner: CliRunner,
    mock_system_checks: Mock,
    mock_profile_manager: Mock,
    mock_home_dir: Mock,
    temp_home: Path,
) -> None:
    """Test profile setup with error."""
    # Create test directory
    test_dir = temp_home / "test_dir"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Mock error
    mock_profile_manager.setup_profile.side_effect = ProfileError("Test error")

    # Execute
    result = runner.invoke(
        cli,
        ["setup"],
        input=f"test\ntest@example.com\ntestuser\n{test_dir}\ngithub\n",
    )

    # Verify
    assert result.exit_code == 1
    assert "Failed: Test error" in result.output


def test_switch_profile(
    runner: CliRunner,
    mock_system_checks: Mock,
    mock_profile_manager: Mock,
    mock_home_dir: Mock,
) -> None:
    """Test switching profiles."""
    # Mock successful profile switch
    profile = Profile(
        name="test",
        email="test@example.com",
        username="testuser",
        directories=[Path("/test/dir")],
        providers=[GitProvider("github")],
        active=True,
    )
    mock_profile_manager.switch_profile.return_value = profile

    # Execute
    result = runner.invoke(cli, ["switch", "test"])

    # Verify
    assert result.exit_code == 0
    assert "Switched to profile 'test'" in result.output


def test_switch_profile_error(
    runner: CliRunner,
    mock_system_checks: Mock,
    mock_profile_manager: Mock,
    mock_home_dir: Mock,
) -> None:
    """Test switching profiles with error."""
    # Mock error
    mock_profile_manager.switch_profile.side_effect = ProfileError("Test error")

    # Execute
    result = runner.invoke(cli, ["switch", "test"])

    # Verify
    assert result.exit_code == 1
    assert "Failed: Test error" in result.output


def test_list_profiles(
    runner: CliRunner,
    mock_system_checks: Mock,
    mock_profile_manager: Mock,
    mock_home_dir: Mock,
) -> None:
    """Test listing profiles."""
    # Mock profiles
    profile = Profile(
        name="test",
        email="test@example.com",
        username="testuser",
        directories=[Path("/test/dir")],
        providers=[GitProvider("github")],
        active=True,
    )
    mock_profile_manager.list_profiles.return_value = [profile]

    # Execute
    result = runner.invoke(cli, ["list"])

    # Verify
    assert result.exit_code == 0
    assert "Git Profiles" in result.output
    assert "test" in result.output
    assert "test@example.com" in result.output
    assert "testuser" in result.output
    assert "/test/dir" in result.output
    assert "github" in result.output
    assert "✓" in result.output
