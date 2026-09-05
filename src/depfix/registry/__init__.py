"""npm registry HTTP client."""

from depfix.registry.client import (
    NpmRegistryClient,
    PackageNotFoundError,
    RegistryError,
    RegistryUnavailableError,
)
from depfix.registry.models import PackageMetadata

__all__ = [
    "NpmRegistryClient",
    "PackageMetadata",
    "PackageNotFoundError",
    "RegistryError",
    "RegistryUnavailableError",
]
