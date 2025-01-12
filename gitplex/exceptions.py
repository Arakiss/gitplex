"""Custom exceptions for GitPlex."""


class GitplexError(Exception):
    """Base exception for GitPlex errors."""
    
    def __init__(self, message: str, details: str | None = None):
        self.message = self._escape_markup(message)
        self.details = self._escape_markup(details) if details else None
        super().__init__(self.message)

    @staticmethod
    def _escape_markup(text: str) -> str:
        """Escape Rich markup in text."""
        return str(text).replace("[", "\\[").replace("]", "\\]")


class ProfileError(GitplexError):
    """Profile management error."""
    pass


class SSHError(GitplexError):
    """Errors related to SSH key management."""
    pass


class GitConfigError(GitplexError):
    """Errors related to Git configuration."""
    pass


class BackupError(GitplexError):
    """Errors related to backup operations."""
    pass


class SystemConfigError(GitplexError):
    """System configuration error."""
    pass
