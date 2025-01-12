"""GitPlex - Seamlessly manage multiple Git identities and workspaces."""

from gitplex.cli import cli, setup, switch, list
from gitplex.profile import ProfileManager
from gitplex.version import __version__

__all__ = ["ProfileManager", "__version__", "cli", "setup", "switch", "list"]
