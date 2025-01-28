"""SSH management and troubleshooting module."""

import subprocess
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from .ui import print_info, print_success, print_warning, print_error
from .exceptions import SSHError

@dataclass
class SSHKeyInfo:
    """Information about an SSH key."""
    name: str
    path: Path
    type: str
    is_in_agent: bool = False
    fingerprint: Optional[str] = None

class SSHManager:
    """Manages SSH operations and troubleshooting."""

    def __init__(self):
        """Initialize SSH manager."""
        self.ssh_dir = Path.home() / ".ssh"
        self.ensure_ssh_dir()

    def ensure_ssh_dir(self) -> None:
        """Ensure SSH directory exists with correct permissions."""
        try:
            self.ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        except Exception as e:
            raise SSHError(f"Could not create SSH directory: {e}")

    def ensure_agent_running(self) -> bool:
        """Ensure SSH agent is running and accessible.
        
        Returns:
            bool: True if agent is running and accessible
        """
        try:
            # First check if SSH_AUTH_SOCK is set
            result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True
            )
            # Code 2 means no agent, 1 means agent with no keys, 0 means agent with keys
            if result.returncode == 2:
                # Try to start the agent
                subprocess.run(
                    ["eval", "`ssh-agent -s`"],
                    shell=True,
                    check=True,
                    executable="/bin/zsh"
                )
            return True
        except subprocess.CalledProcessError:
            return False

    def get_key_fingerprint(self, key_path: Path) -> Optional[str]:
        """Get the fingerprint of an SSH key.
        
        Args:
            key_path: Path to the private key
            
        Returns:
            str: Fingerprint if successful, None otherwise
        """
        try:
            result = subprocess.run(
                ["ssh-keygen", "-l", "-f", str(key_path)],
                capture_output=True,
                text=True,
                check=True
            )
            # Output format: <bits> <fingerprint> <path> (<type>)
            return result.stdout.split()[1]
        except subprocess.CalledProcessError:
            return None

    def get_key_info(self, key_path: Path) -> Optional[SSHKeyInfo]:
        """Get information about an SSH key.
        
        Args:
            key_path: Path to the private key
            
        Returns:
            SSHKeyInfo if key exists, None otherwise
        """
        if not key_path.exists():
            return None

        try:
            # Get key fingerprint and type
            result = subprocess.run(
                ["ssh-keygen", "-l", "-f", str(key_path)],
                capture_output=True,
                text=True,
                check=True
            )
            # Output format: <bits> <fingerprint> <path> (<type>)
            parts = result.stdout.strip().split()
            fingerprint = parts[1]
            key_type = parts[-1].strip("()") if len(parts) >= 4 else "unknown"

            # Check if key is in agent by comparing fingerprints
            agent_result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True
            )
            is_in_agent = fingerprint in agent_result.stdout

            return SSHKeyInfo(
                name=key_path.name,
                path=key_path,
                type=key_type,
                is_in_agent=is_in_agent,
                fingerprint=fingerprint
            )
        except subprocess.CalledProcessError:
            return None

    def add_key_to_agent(self, key_path: Path) -> Tuple[bool, str]:
        """Add a key to the SSH agent.
        
        Args:
            key_path: Path to the private key
            
        Returns:
            Tuple of (success, message)
        """
        if not self.ensure_agent_running():
            return False, "SSH agent is not running and could not be started"

        try:
            # Get key fingerprint
            key_fingerprint = self.get_key_fingerprint(key_path)
            if not key_fingerprint:
                return False, "Could not get key fingerprint"

            # Check if key is already in agent by fingerprint
            agent_result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True
            )
            if key_fingerprint in agent_result.stdout:
                return True, "Key is already in agent"

            # Add key to agent
            add_result = subprocess.run(
                ["ssh-add", str(key_path)],
                capture_output=True,
                text=True,
                check=True
            )
            return True, "Key added to agent successfully"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            return False, f"Failed to add key to agent: {error_msg}"

    def fix_key_permissions(self, key_path: Path) -> Tuple[bool, str]:
        """Fix SSH key permissions.
        
        Args:
            key_path: Path to the private key
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Private key should be 600
            key_path.chmod(0o600)
            # Public key should be 644
            key_path.with_suffix(key_path.suffix + '.pub').chmod(0o644)
            return True, "Key permissions fixed"
        except Exception as e:
            return False, f"Failed to fix key permissions: {e}"

    def troubleshoot_key(self, key_path: Path) -> list[str]:
        """Troubleshoot SSH key issues.
        
        Args:
            key_path: Path to the private key
            
        Returns:
            List of actions taken or recommended
        """
        actions = []
        
        # Check if key exists
        if not key_path.exists():
            actions.append("Key file not found")
            return actions

        # Check and fix permissions
        success, msg = self.fix_key_permissions(key_path)
        if success:
            actions.append("Fixed key permissions")
        else:
            actions.append(f"Permission issue: {msg}")

        # Check and start agent if needed
        if not self.ensure_agent_running():
            actions.append("Could not start SSH agent")
            return actions

        # Try to add key to agent
        success, msg = self.add_key_to_agent(key_path)
        if success:
            actions.append("Added key to SSH agent")
        else:
            actions.append(f"Agent issue: {msg}")

        return actions

    def verify_key_setup(self, key_path: Path) -> bool:
        """Verify complete SSH key setup.
        
        Args:
            key_path: Path to the private key
            
        Returns:
            bool: True if setup is correct
        """
        # First check if the key exists
        if not key_path.exists():
            print_warning("SSH key file not found")
            return False

        # Check permissions
        try:
            stat = key_path.stat()
            if stat.st_mode & 0o777 != 0o600:
                print_warning(f"Incorrect private key permissions: {stat.st_mode & 0o777:o}")
                return False
            
            pub_key = key_path.with_suffix(key_path.suffix + '.pub')
            if not pub_key.exists():
                print_warning("Public key file not found")
                return False
                
            pub_stat = pub_key.stat()
            if pub_stat.st_mode & 0o777 != 0o644:
                print_warning(f"Incorrect public key permissions: {pub_stat.st_mode & 0o777:o}")
                return False
        except Exception as e:
            print_warning(f"Error checking key permissions: {e}")
            return False

        # Get key info
        key_info = self.get_key_info(key_path)
        if not key_info:
            print_warning("Could not get key information")
            return False

        # Check if in agent
        if not key_info.is_in_agent:
            print_warning("Key is not loaded in SSH agent")
            return False

        return True 