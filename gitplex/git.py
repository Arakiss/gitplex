"""Git configuration management functionality."""

import configparser
from pathlib import Path
import subprocess

from .exceptions import SystemConfigError


class GitConfig:
    """Git configuration manager."""

    def __init__(self) -> None:
        """Initialize Git configuration manager."""
        self.home_dir = Path.home()
        self.config_path = self.home_dir / ".gitconfig"

    def setup(self, name: str, email: str, username: str) -> None:
        """Set up Git configuration.

        Args:
            name: Profile name
            email: Git email
            username: Git username
        """
        try:
            self._update_config(name, email, username)
        except (OSError, configparser.Error) as e:
            raise SystemConfigError("Failed to setup Git config", str(e))

    def update(self, name: str, email: str, username: str) -> None:
        """Update Git configuration.

        Args:
            name: Profile name
            email: Git email
            username: Git username
        """
        try:
            self._update_config(name, email, username)
        except (OSError, configparser.Error) as e:
            raise SystemConfigError("Failed to update Git config", str(e))

    def _update_config(self, name: str, email: str, username: str) -> None:
        """Update Git configuration file.

        Args:
            name: Profile name
            email: Git email
            username: Git username
        """
        # Create parent directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config file if it doesn't exist
        if not self.config_path.exists():
            self.config_path.touch()

        # Read existing config
        config = configparser.ConfigParser()
        config.read(self.config_path)

        # Update user section
        if "user" not in config:
            config["user"] = {}
        config["user"]["name"] = name
        config["user"]["email"] = email
        config["user"]["username"] = username

        # Write config
        with self.config_path.open("w") as f:
            config.write(f)

        # Set permissions
        self.config_path.chmod(0o644)


def update_gitconfig(
    config_path: Path,
    name: str,
    email: str,
    username: str,
) -> None:
    """Update Git configuration file.

    Args:
        config_path: Path to Git config file
        name: Profile name
        email: Git email
        username: Git username
    """
    try:
        # Create parent directory if it doesn't exist
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create config file if it doesn't exist
        if not config_path.exists():
            config_path.touch()

        # Read existing config
        config = configparser.ConfigParser()
        config.read(config_path)

        # Update user section
        if "user" not in config:
            config["user"] = {}
        config["user"]["name"] = name
        config["user"]["email"] = email
        config["user"]["username"] = username

        # Write config
        with config_path.open("w") as f:
            config.write(f)

        # Set permissions
        config_path.chmod(0o644)

    except (OSError, configparser.Error) as e:
        raise SystemConfigError(
            "Failed to update Git config",
            details=f"Path: {config_path}, Error: {e}",
        )


def create_directory_gitconfig(
    directory: Path,
    name: str,
    email: str,
    username: str,
) -> None:
    """Create Git configuration file for a directory.

    Args:
        directory: Directory path
        name: Profile name
        email: Git email
        username: Git username
    """
    try:
        # Create parent directory if it doesn't exist
        directory.mkdir(parents=True, exist_ok=True)

        # Create Git config
        config_path = directory / ".git" / "config"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.touch()
        config_path.chmod(0o644)

        # Update Git config
        subprocess.run(
            ["git", "config", "--file", str(config_path), "user.name", username],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "--file", str(config_path), "user.email", email],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise SystemConfigError(
            "Failed to update Git config",
            details=f"Command: {' '.join(e.cmd)}\nOutput: {e.stdout}\nError: {e.stderr}",
        )
    except OSError as e:
        raise SystemConfigError(
            "Failed to create Git config file",
            details=f"Path: {config_path}, Error: {e}",
        )
