"""Git provider management."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class ProviderType(Enum):
    """Supported Git providers."""
    GITHUB = auto()
    GITLAB = auto()
    BITBUCKET = auto()

    @classmethod
    def from_str(cls, value: str) -> "ProviderType":
        """Convert string to provider type."""
        mapping = {
            "github": cls.GITHUB,
            "gitlab": cls.GITLAB,
            "bitbucket": cls.BITBUCKET,
        }
        normalized = value.lower().strip()
        if normalized not in mapping:
            raise ValueError(f"Invalid provider: {value}")
        return mapping[normalized]

    def __str__(self) -> str:
        """Convert provider type to string."""
        return self.name.lower()


@dataclass
class Provider:
    """Git provider configuration."""
    type: ProviderType
    ssh_host: str = ""
    api_url: str = ""

    @property
    def name(self) -> str:
        """Get provider name."""
        return str(self.type)

    @classmethod
    def create(cls, provider_type: str) -> "Provider":
        """Create a provider from string type."""
        ptype = ProviderType.from_str(provider_type)
        
        # Configure provider-specific settings
        if ptype == ProviderType.GITHUB:
            return cls(
                type=ptype,
                ssh_host="github.com",
                api_url="https://api.github.com",
            )
        elif ptype == ProviderType.GITLAB:
            return cls(
                type=ptype,
                ssh_host="gitlab.com",
                api_url="https://gitlab.com/api/v4",
            )
        elif ptype == ProviderType.BITBUCKET:
            return cls(
                type=ptype,
                ssh_host="bitbucket.org",
                api_url="https://api.bitbucket.org/2.0",
            )
        
        raise ValueError(f"Unsupported provider type: {provider_type}")


class ProviderManager:
    """Manages Git providers for a profile."""

    def __init__(self) -> None:
        """Initialize provider manager."""
        self.providers: List[Provider] = []

    def add_provider(self, provider_type: str) -> None:
        """Add a provider if not already present."""
        provider = Provider.create(provider_type)
        if not self.has_provider(provider.type):
            self.providers.append(provider)

    def has_provider(self, provider_type: ProviderType) -> bool:
        """Check if a provider type is already added."""
        return any(p.type == provider_type for p in self.providers)

    def get_provider_names(self) -> List[str]:
        """Get list of provider names."""
        return [str(p.type) for p in self.providers]

    @staticmethod
    def get_available_providers() -> List[str]:
        """Get list of available provider names."""
        return [str(p) for p in ProviderType]

    def get_ssh_config(self) -> str:
        """Generate SSH config for all providers."""
        config = []
        for provider in self.providers:
            config.append(f"Host {provider.ssh_host}")
            config.append("  User git")
            config.append("  IdentityFile ~/.ssh/id_%h")
            config.append("")
        return "\n".join(config) 