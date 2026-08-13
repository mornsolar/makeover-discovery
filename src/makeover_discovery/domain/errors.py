"""Domain-level error taxonomy.

Every layer above translates these into its own vocabulary: the API maps them to
status codes, the CLI to exit codes. Nothing in ``domain`` knows either exists.
"""

from __future__ import annotations


class MakeoverError(Exception):
    """Base class for every error this system raises deliberately."""


class ValidationError(MakeoverError):
    """Input violated a domain rule."""


class NotFoundError(MakeoverError):
    """A referenced entity does not exist."""


class UpstreamError(MakeoverError):
    """A third-party provider failed or returned something unusable."""


class ConfigurationError(MakeoverError):
    """A capability was requested that this deployment is not configured for.

    Distinct from ``ValidationError``: the request was fine, the operator's
    configuration is not, so it maps to a server error rather than a client one.
    """


class PolicyViolationError(MakeoverError):
    """An action was refused by a licensing, retention, or robots policy.

    Separate from ``ValidationError`` because the remedy differs: the caller
    cannot fix this by sending different input.
    """
