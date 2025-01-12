"""Custom exceptions for GitPlex."""



class GitPlexError(Exception):
    """Base exception for all GitPlex errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        """Initialize the error.
        
        Args:
            message: Main error message
            details: Optional detailed explanation
        """
        self.message = message
        self.details = details
        super().__init__(message)


class ProfileError(GitPlexError):
    """Errors related to profile management."""
    pass


class SSHError(GitPlexError):
    """Errors related to SSH key management."""
    pass


class GitConfigError(GitPlexError):
    """Errors related to Git configuration."""
    pass


class BackupError(GitPlexError):
    """Errors related to backup operations."""
    pass


class SystemConfigError(GitPlexError):
    """Errors related to system configuration."""
    pass
