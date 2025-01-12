"""Tests for profile management functionality."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from gitplex.exceptions import ProfileError
from gitplex.profile import GitProvider, Profile, ProfileManager


@pytest.fixture
def temp_home(tmp_path: Path) -> Path:
    """Create temporary home directory."""
    with patch.dict("os.environ", {"GITPLEX_TEST_HOME": str(tmp_path)}):
        yield tmp_path


@pytest.fixture
def mock_git_config() -> Mock:
    """Mock Git configuration."""
    with patch("gitplex.profile.GitConfig") as mock:
        yield mock.return_value


@pytest.fixture
def mock_ssh_config() -> Mock:
    """Mock SSH configuration."""
    with patch("gitplex.profile.SSHConfig") as mock:
        yield mock.return_value


@pytest.fixture
def profile_manager(temp_home: Path, mock_git_config: Mock, mock_ssh_config: Mock) -> ProfileManager:
    """Create profile manager."""
    config_dir = temp_home / ".config" / "gitplex"
    return ProfileManager(config_dir=config_dir)


def test_create_profile(profile_manager: ProfileManager, temp_home: Path) -> None:
    """Test creating a new profile."""
    # Setup
    name = "test"
    email = "test@example.com"
    username = "testuser"
    directories = [str(temp_home / "projects/personal")]
    providers = ["github", "gitlab"]

    # Create test directories
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

    # Execute
    profile = profile_manager.setup_profile(
        name=name,
        email=email,
        username=username,
        directories=directories,
        providers=providers,
    )

    # Verify profile was created correctly
    assert profile.name == name
    assert profile.email == email
    assert profile.username == username
    assert len(profile.directories) == 1
    assert str(profile.directories[0]) == str(Path(directories[0]).expanduser())
    assert len(profile.providers) == 2
    assert all(isinstance(p, GitProvider) for p in profile.providers)

    # Verify profile was saved
    profiles_file = profile_manager.profiles_file
    assert profiles_file.exists()
    data = json.loads(profiles_file.read_text())
    assert name in data
    assert data[name]["email"] == email

    # Verify Git and SSH configurations were updated
    profile_manager.git_config.setup.assert_called_once_with(name, email, username)
    profile_manager.ssh_config.setup.assert_called_once_with(name, username, providers)


def test_switch_profile(profile_manager: ProfileManager, temp_home: Path) -> None:
    """Test switching between profiles."""
    # Setup - create two profiles
    test_dir1 = temp_home / "test_dir1"
    test_dir2 = temp_home / "test_dir2"

    # Create test directories
    test_dir1.mkdir(parents=True, exist_ok=True)
    test_dir2.mkdir(parents=True, exist_ok=True)

    profile1 = profile_manager.setup_profile(
        name="personal",
        email="personal@example.com",
        username="personal-user",
        directories=[str(test_dir1)],
        providers=["github"],
    )
    profile2 = profile_manager.setup_profile(
        name="work",
        email="work@company.com",
        username="work-user",
        directories=[str(test_dir2)],
        providers=["gitlab"],
    )

    # Execute - switch to work profile
    active_profile = profile_manager.switch_profile("work")

    # Verify profile was switched correctly
    assert active_profile.name == "work"
    assert active_profile.active
    assert not profile1.active

    # Verify Git and SSH configurations were updated
    profile_manager.git_config.update.assert_called_with(
        "work", "work@company.com", "work-user"
    )
    profile_manager.ssh_config.update.assert_called_with(
        "work", "work-user", ["gitlab"]
    )


def test_list_profiles(profile_manager: ProfileManager, temp_home: Path) -> None:
    """Test listing profiles."""
    # Setup - create two profiles
    test_dir1 = temp_home / "test_dir1"
    test_dir2 = temp_home / "test_dir2"

    test_dir1.mkdir(parents=True, exist_ok=True)
    test_dir2.mkdir(parents=True, exist_ok=True)

    profile_manager.setup_profile(
        name="personal",
        email="personal@example.com",
        username="personal-user",
        directories=[str(test_dir1)],
        providers=["github"],
    )
    profile_manager.setup_profile(
        name="work",
        email="work@company.com",
        username="work-user",
        directories=[str(test_dir2)],
        providers=["gitlab"],
    )

    # Execute
    profiles = profile_manager.list_profiles()

    # Verify
    assert len(profiles) == 2
    assert any(p.name == "personal" for p in profiles)
    assert any(p.name == "work" for p in profiles)


def test_get_active_profile(profile_manager: ProfileManager, temp_home: Path) -> None:
    """Test getting active profile."""
    # Setup - create two profiles
    test_dir = temp_home / "test_dir"
    test_dir.mkdir(parents=True, exist_ok=True)

    profile_manager.setup_profile(
        name="test",
        email="test@example.com",
        username="testuser",
        directories=[str(test_dir)],
        providers=["github"],
    )

    # Execute - switch profile
    profile_manager.switch_profile("test")

    # Verify
    active_profile = profile_manager.get_active_profile()
    assert active_profile is not None
    assert active_profile.name == "test"
