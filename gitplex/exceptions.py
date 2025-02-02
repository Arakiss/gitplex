"""Custom exceptions for GitPlex."""


class GitplexError(Exception):
    """Base exception for GitPlex."""
    
    def __init__(self, message: str, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)

    @staticmethod
    def _escape_markup(text: str) -> str:
        """Escape Rich markup in text."""
        return str(text).replace("[", "\\[").replace("]", "\\]")

    def __str__(self) -> str:
        return self.message


class ProfileError(GitplexError):
    """Profile-related errors."""
    
    def __init__(
        self,
        message: str,
        profile_name: str | None = None,
        current_config: dict | None = None,
    ) -> None:
        self.profile_name = profile_name
        self.current_config = current_config
        super().__init__(message)


class SSHError(GitplexError):
    """Errors related to SSH key management."""
    pass


class GitConfigError(GitplexError):
    """Errors related to Git configuration."""
    pass


class BackupError(GitplexError):
    """Backup-related errors."""
    pass


class SystemConfigError(GitplexError):
    """System configuration errors."""
    pass
