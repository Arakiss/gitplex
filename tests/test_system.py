"""Tests for system utilities and backup functionality."""

import json
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest

from gitplex.exceptions import BackupError, SystemConfigError
from gitplex.system import (
    check_git_installation,
    check_ssh_agent,
    check_system_compatibility,
    create_backup,
    get_existing_configs,
    restore_backup,
)


@pytest.fixture
def temp_home(tmp_path) -> Generator[Path, None, None]:
    """Create a temporary home directory."""
    yield tmp_path


@pytest.fixture
def mock_subprocess(monkeypatch) -> None:
    """Mock subprocess calls."""
    def mock_run(cmd, *args, **kwargs):
        if cmd[0] == "git":
            return subprocess.CompletedProcess(
                cmd,
                returncode=0,
                stdout="git version 2.39.2\n",
                stderr="",
            )
        elif cmd[0] == "ssh-add":
            return subprocess.CompletedProcess(
                cmd,
                returncode=0,
                stdout="",
                stderr="",
            )
        return subprocess.CompletedProcess(
            cmd,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", mock_run)


def test_check_git_installation(mock_subprocess) -> None:
    """Test Git installation check."""
    installed, version = check_git_installation()
    assert installed
    assert "git version" in version


def test_check_git_installation_not_found(monkeypatch) -> None:
    """Test Git installation check when Git is not installed."""
    def mock_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(SystemConfigError, match="Git is not installed"):
        check_git_installation()


def test_check_ssh_agent(mock_subprocess) -> None:
    """Test SSH agent check."""
    assert check_ssh_agent()


def test_check_ssh_agent_not_running(monkeypatch) -> None:
    """Test SSH agent check when agent is not running."""
    def mock_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(SystemConfigError, match="SSH is not installed"):
        check_ssh_agent()


def test_get_existing_configs(temp_home: Path, monkeypatch) -> None:
    """Test getting existing configurations."""
    monkeypatch.setattr("pathlib.Path.home", lambda: temp_home)

    # Create test configs
    ssh_dir = temp_home / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "config").touch()

    git_config = temp_home / ".gitconfig"
    git_config.touch()

    configs = get_existing_configs()
    assert len(configs) == 3
    assert "git_config" in configs
    assert "ssh_config" in configs
    assert "ssh_keys" in configs


def test_create_backup(temp_home: Path) -> None:
    """Test creating backup."""
    # Create test configs
    ssh_dir = temp_home / ".ssh"
    ssh_dir.mkdir()
    ssh_config = ssh_dir / "config"
    ssh_config.write_text("test ssh config")

    git_config = temp_home / ".gitconfig"
    git_config.write_text("test git config")

    # Create backup
    configs = {
        "git_config": git_config,
        "ssh_config": ssh_config,
        "ssh_keys": ssh_dir,
    }
    backup_path = create_backup(configs, backup_dir=temp_home / "backups")

    # Verify backup
    assert backup_path.exists()
    assert (backup_path / "config").read_text() == "test ssh config"
    assert (backup_path / ".gitconfig").read_text() == "test git config"
    assert (backup_path / "metadata.json").exists()


def test_restore_backup(temp_home: Path) -> None:
    """Test restoring backup."""
    # Create a backup first
    backup_dir = temp_home / "backup"
    backup_dir.mkdir()

    # Create target directories
    ssh_dir = temp_home / ".ssh"
    ssh_dir.mkdir(parents=True)

    # Create backup files
    (backup_dir / ".gitconfig").write_text("restored git config")
    (backup_dir / "config").write_text("restored ssh config")

    metadata = {
        "timestamp": "20240112_120000",
        "configs": {
            "git_config": str(temp_home / ".gitconfig"),
            "ssh_config": str(temp_home / ".ssh" / "config"),
        }
    }
    (backup_dir / "metadata.json").write_text(json.dumps(metadata))

    # Restore backup
    restore_backup(backup_dir)

    # Verify restoration
    assert (temp_home / ".gitconfig").read_text() == "restored git config"
    assert (temp_home / ".ssh" / "config").read_text() == "restored ssh config"


def test_restore_backup_invalid_metadata(temp_home: Path) -> None:
    """Test restoring backup with invalid metadata."""
    backup_dir = temp_home / "backup"
    backup_dir.mkdir()
    (backup_dir / "metadata.json").write_text("invalid json")

    with pytest.raises(BackupError, match="Failed to restore backup"):
        restore_backup(backup_dir)


def test_check_system_compatibility(mock_subprocess, temp_home: Path, monkeypatch) -> None:
    """Test system compatibility check."""
    monkeypatch.setattr("pathlib.Path.home", lambda: temp_home)
    check_system_compatibility()  # Should not raise any exceptions


def test_check_system_compatibility_no_git(monkeypatch) -> None:
    """Test system compatibility check without Git."""
    def mock_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("subprocess.run", mock_run)

    with pytest.raises(SystemConfigError, match="System compatibility check failed"):
        check_system_compatibility()
