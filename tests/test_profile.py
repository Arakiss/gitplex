"""Tests for profile management functionality."""

import json
from pathlib import Path
from typing import Generator

import pytest
from pydantic import BaseModel

from gitplex.profile import GitProvider, Profile, ProfileManager


@pytest.fixture
def temp_home(tmp_path) -> Generator[Path, None, None]:
    """Create a temporary home directory."""
    yield tmp_path


@pytest.fixture
def profile_manager(temp_home: Path) -> ProfileManager:
    """Create a ProfileManager instance with a temporary config directory."""
    return ProfileManager(config_dir=temp_home / ".gitplex")


def test_create_profile(profile_manager: ProfileManager, temp_home: Path) -> None:
    """Test creating a new profile."""
    # Setup
    name = "test"
    email = "test@example.com"
    username = "testuser"
    directories = [str(temp_home / "projects/personal")]
    providers = ["github", "gitlab"]

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
    assert all(isinstance(p, (str, GitProvider)) for p in profile.providers)

    # Verify profile was saved
    profiles_file = profile_manager.profiles_file
    assert profiles_file.exists()
    data = json.loads(profiles_file.read_text())
    assert name in data
    assert data[name]["email"] == email

    # Verify SSH keys were created
    ssh_dir = temp_home / ".ssh"
    for provider in providers:
        key_path = ssh_dir / f"{name}_{provider}"
        assert key_path.exists()
        assert key_path.with_suffix(".pub").exists()

    # Verify Git configs were created
    for directory in profile.directories:
        config_path = directory / ".gitconfig"
        assert config_path.exists()


def test_list_profiles(profile_manager: ProfileManager) -> None:
    """Test listing profiles."""
    # Setup - create two profiles
    profile1 = profile_manager.setup_profile(
        name="personal",
        email="personal@example.com",
        username="personal-user",
    )
    profile2 = profile_manager.setup_profile(
        name="work",
        email="work@company.com",
        username="work-user",
    )

    # Execute
    profiles = profile_manager.list_profiles()

    # Verify
    assert len(profiles) == 2
    assert any(p.name == "personal" for p in profiles)
    assert any(p.name == "work" for p in profiles)


def test_switch_profile(profile_manager: ProfileManager, temp_home: Path) -> None:
    """Test switching between profiles."""
    # Setup - create two profiles
    profile1 = profile_manager.setup_profile(
        name="personal",
        email="personal@example.com",
        username="personal-user",
    )
    profile2 = profile_manager.setup_profile(
        name="work",
        email="work@company.com",
        username="work-user",
    )

    # Execute - switch to work profile
    active_profile = profile_manager.switch_profile("work")

    # Verify
    assert active_profile.name == "work"
    global_config = temp_home / ".gitconfig"
    assert global_config.exists()
    content = global_config.read_text()
    assert "work@company.com" in content
    assert "work-user" in content


def test_switch_nonexistent_profile(profile_manager: ProfileManager) -> None:
    """Test switching to a non-existent profile raises an error."""
    with pytest.raises(ValueError, match="Profile 'nonexistent' not found"):
        profile_manager.switch_profile("nonexistent") 