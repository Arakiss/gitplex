"""System utilities for GitPlex."""

import os
import platform
import subprocess
from enum import Enum, auto
from pathlib import Path
from typing import Optional, Dict

from .ui import print_error, print_info, print_success, print_warning


class SystemType(Enum):
    """Supported system types."""
    LINUX = auto()
    MACOS = auto()
    WSL = auto()
    UNKNOWN = auto()

    @classmethod
    def detect(cls) -> "SystemType":
        """Detect the current system type."""
        system = platform.system().lower()
        
        if system == "darwin":
            return cls.MACOS
        elif system == "linux":
            # Check if running under WSL
            try:
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        return cls.WSL
            except:
                pass
            return cls.LINUX
        
        return cls.UNKNOWN


class SSHAgentManager:
    """Manages SSH agent across different systems."""
    
    def __init__(self) -> None:
        """Initialize SSH agent manager."""
        self.system = SystemType.detect()
        self._env_vars: Dict[str, str] = {}
    
    @property
    def env_vars(self) -> Dict[str, str]:
        """Get SSH agent environment variables."""
        return self._env_vars.copy()
    
    def is_running(self) -> bool:
        """Check if SSH agent is running."""
        try:
            # Primero verificar si las variables de entorno están configuradas
            if 'SSH_AUTH_SOCK' not in os.environ:
                return False
            
            # Intentar usar el agente
            result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True,
                env=os.environ
            )
            
            # El código 1 significa "no hay claves" pero el agente está corriendo
            # El código 2 significa "no se puede conectar al agente"
            return result.returncode in [0, 1]
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False
    
    def start(self) -> bool:
        """Start SSH agent if not running."""
        if self.is_running():
            print_success("SSH agent is already running")
            return True
        
        print_warning("SSH agent is not running, starting it...")
        
        try:
            if self.system == SystemType.WSL:
                # WSL requires special handling
                return self._start_wsl()
            else:
                # Standard Unix/MacOS approach
                return self._start_unix()
        except Exception as e:
            print_error(f"Failed to start SSH agent: {e}")
            self._show_manual_instructions()
            return False
    
    def _start_unix(self) -> bool:
        """Start SSH agent on Unix-like systems."""
        try:
            # Start agent and capture output
            agent_output = subprocess.check_output(
                ["ssh-agent", "-s"],
                text=True
            )
            
            # Parse environment variables
            for line in agent_output.splitlines():
                if "=" in line and ";" in line:
                    var = line.split("=", 1)[0]
                    value = line.split("=", 1)[1].split(";", 1)[0]
                    os.environ[var] = value
                    self._env_vars[var] = value
            
            return self.is_running()
        except subprocess.CalledProcessError:
            return False
    
    def _start_wsl(self) -> bool:
        """Start SSH agent on WSL."""
        try:
            # Use eval to properly set up the agent
            agent_cmd = "eval `ssh-agent -s` > /dev/null && echo $SSH_AUTH_SOCK && echo $SSH_AGENT_PID"
            agent_output = subprocess.check_output(
                agent_cmd,
                shell=True,
                text=True
            )
            
            # Parse output (SSH_AUTH_SOCK in first line, SSH_AGENT_PID in second)
            lines = agent_output.strip().split('\n')
            if len(lines) >= 2:
                os.environ['SSH_AUTH_SOCK'] = lines[0]
                os.environ['SSH_AGENT_PID'] = lines[1]
                self._env_vars['SSH_AUTH_SOCK'] = lines[0]
                self._env_vars['SSH_AGENT_PID'] = lines[1]
            
            return self.is_running()
        except subprocess.CalledProcessError:
            return False
    
    def add_key(self, key_path: Path) -> bool:
        """Add a key to the SSH agent."""
        try:
            subprocess.run(
                ["ssh-add", str(key_path)],
                check=True,
                env=os.environ
            )
            print_success(f"Added key: {key_path}")
            return True
        except subprocess.CalledProcessError as e:
            print_warning(f"Could not add key {key_path}: {e}")
            return False
    
    def add_keys(self, pattern: str = "id_*") -> None:
        """Add all matching keys to the SSH agent."""
        ssh_dir = Path.home() / ".ssh"
        for key_file in ssh_dir.glob(pattern):
            if not key_file.name.endswith(".pub"):
                self.add_key(key_file)
    
    def is_key_loaded(self, key_path: Path) -> bool:
        """Check if a specific key is loaded in the agent."""
        try:
            agent_output = subprocess.check_output(
                ["ssh-add", "-l"],
                text=True,
                env=os.environ
            )
            return str(key_path) in agent_output
        except subprocess.CalledProcessError:
            return False
    
    def _show_manual_instructions(self) -> None:
        """Show instructions for manual SSH agent setup."""
        print_info("Please try starting the SSH agent manually:")
        if self.system == SystemType.WSL:
            print_info("1. Run: eval `ssh-agent -s`")
        else:
            print_info("1. Run: ssh-agent -s")
        print_info("2. Add your keys: ssh-add ~/.ssh/id_*")


def get_ssh_agent() -> SSHAgentManager:
    """Get an SSH agent manager instance."""
    return SSHAgentManager() 