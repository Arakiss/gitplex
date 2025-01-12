"""Integration tests for complete user workflows."""

import os
from pathlib import Path

import pytest

from gitplex.exceptions import ProfileError
from gitplex.profile import ProfileManager


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace for testing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Set up environment
    os.environ["HOME"] = str(workspace)
    os.environ["GITPLEX_TEST_HOME"] = str(workspace)

    # Create SSH directory
    ssh_dir = workspace / ".ssh"
    ssh_dir.mkdir()

    return workspace


@pytest.fixture
def temp_git_repo(temp_workspace: Path) -> Path:
    """Create a temporary Git repository."""
    repo_path = temp_workspace / "test-repo"
    repo_path.mkdir()
    os.chdir(repo_path)
    os.system("git init")
    return repo_path


def test_complete_profile_workflow(temp_workspace: Path, temp_git_repo: Path) -> None:
    """Test a complete profile workflow from setup to commit verification."""
    # Setup profile manager with test config directory
    config_dir = temp_workspace / ".config" / "gitplex"
    profile_manager = ProfileManager(config_dir=config_dir)

    # 1. Create personal profile
    personal_profile = profile_manager.setup_profile(
        name="personal",
        email="personal@example.com",
        username="personal-user",
        directories=[str(temp_workspace / "personal")],
        providers=["github"],
    )

    assert personal_profile.name == "personal"
    assert personal_profile.email == "personal@example.com"

    # Verify Git config was created
    gitconfig = temp_workspace / ".gitconfig"
    assert gitconfig.exists()
    assert "personal@example.com" in gitconfig.read_text()

    # 2. Create work profile
    work_profile = profile_manager.setup_profile(
        name="work",
        email="work@company.com",
        username="work-user",
        directories=[str(temp_workspace / "work")],
        providers=["gitlab"],
    )

    assert work_profile.name == "work"
    assert work_profile.email == "work@company.com"

    # 3. Switch to personal profile and make a commit
    profile_manager.switch_profile("personal")
    with open(temp_git_repo / "test.txt", "w") as f:
        f.write("test content")

    os.system("git add test.txt")
    os.system(
        'git -c "user.name=personal-user" -c "user.email=personal@example.com" '
        'commit -m "test commit"',
    )

    # Verify commit author
    result = os.popen("git log -1 --pretty=format:'%an <%ae>'").read()
    assert "personal-user <personal@example.com>" in result

    # 4. Switch to work profile
    profile_manager.switch_profile("work")

    # Verify Git config was updated
    gitconfig = temp_workspace / ".gitconfig"
    assert gitconfig.exists()
    gitconfig_content = gitconfig.read_text()
    assert "work@company.com" in gitconfig_content
    assert "work-user" in gitconfig_content

    # 5. Make another commit with work profile
    with open(temp_git_repo / "test2.txt", "w") as f:
        f.write("test content 2")

    os.system("git add test2.txt")
    os.system(
        'git -c "user.name=work-user" -c "user.email=work@company.com" '
        'commit -m "test commit 2"',
    )

    # Verify second commit author
    result = os.popen("git log -1 --pretty=format:'%an <%ae>'").read()
    assert "work-user <work@company.com>" in result


def test_profile_switching_updates_configs(temp_workspace: Path) -> None:
    """Test that switching profiles correctly updates all configurations."""
    config_dir = temp_workspace / ".config" / "gitplex"
    profile_manager = ProfileManager(config_dir=config_dir)

    # Setup profiles
    profile_manager.setup_profile(
        name="personal",
        email="personal@example.com",
        username="personal-user",
        directories=[str(temp_workspace / "personal")],
        providers=["github"],
    )

    profile_manager.setup_profile(
        name="work",
        email="work@company.com",
        username="work-user",
        directories=[str(temp_workspace / "work")],
        providers=["gitlab"],
    )

    # Switch to personal and verify configs
    profile_manager.switch_profile("personal")

    gitconfig = temp_workspace / ".gitconfig"
    assert gitconfig.exists()
    gitconfig_content = gitconfig.read_text()
    assert "personal@example.com" in gitconfig_content
    assert "personal-user" in gitconfig_content

    sshconfig = temp_workspace / ".ssh" / "config"
    assert sshconfig.exists()
    sshconfig_content = sshconfig.read_text()
    assert "personal_github" in sshconfig_content

    # Switch to work and verify configs
    profile_manager.switch_profile("work")

    gitconfig_content = gitconfig.read_text()
    assert "work@company.com" in gitconfig_content
    assert "work-user" in gitconfig_content

    sshconfig_content = sshconfig.read_text()
    assert "work_gitlab" in sshconfig_content


def test_invalid_profile_operations(temp_workspace: Path) -> None:
    """Test error handling for invalid profile operations."""
    config_dir = temp_workspace / ".config" / "gitplex"
    profile_manager = ProfileManager(config_dir=config_dir)

    # Try to switch to non-existent profile
    with pytest.raises(ProfileError, match="Profile 'nonexistent' not found"):
        profile_manager.switch_profile("nonexistent")

    # Create a profile
    profile_manager.setup_profile(
        name="test",
        email="test@example.com",
        username="test-user",
        directories=[str(temp_workspace / "test")],
        providers=["github"],
    )

    # Try to create duplicate profile
    with pytest.raises(ProfileError, match="Profile 'test' already exists"):
        profile_manager.setup_profile(
            name="test",
            email="test2@example.com",
            username="test-user2",
            directories=[str(temp_workspace / "test2")],
            providers=["github"],
        )
