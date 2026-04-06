"""cfdiclient.config — ClientConfig: all tunable parameters for the library.

This is a pure value object. No logic lives here. Every constant that
appears in multiple modules should be referenced via ClientConfig rather
than duplicated.
"""
from __future__ import annotations

import warnings

from pydantic import BaseModel, Field, model_validator


class InsecureConfigurationWarning(UserWarning):
    """Raised when a security-sensitive configuration option is set to an unsafe value.

    Applications can promote this to an error in production with::

        import warnings
        warnings.filterwarnings("error", category=InsecureConfigurationWarning)
    """


class ClientConfig(BaseModel):
    """Immutable configuration for CFDIClient and all service classes.

    All fields have production-safe defaults. Pass an instance to the client
    or individual service constructors to override any value.
    """

    model_config = {"frozen": True}

    # HTTP
    request_timeout: float = Field(
        default=30.0,
        description="Seconds before an HTTP request times out.",
        gt=0,
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SAT TLS certificates. Never disable in production.",
    )

    @model_validator(mode="after")
    def _warn_if_ssl_disabled(self) -> "ClientConfig":
        # SECURITY: Emit an InsecureConfigurationWarning when verify_ssl=False
        # so that accidental production use is surfaced immediately.
        # Tests can suppress this with:
        #   warnings.filterwarnings("ignore", category=InsecureConfigurationWarning)
        # Production code can promote it to an error with:
        #   warnings.filterwarnings("error", category=InsecureConfigurationWarning)
        if not self.verify_ssl:
            warnings.warn(
                "ClientConfig: verify_ssl=False disables TLS certificate "
                "verification for all SAT requests. This must never be used "
                "in production — it exposes FIEL signatures and auth tokens "
                "to interception. Use verify_ssl=True (the default).",
                InsecureConfigurationWarning,
                stacklevel=2,
            )
        return self

    # Token lifecycle
    token_buffer_seconds: int = Field(
        default=270,
        description=(
            "Treat a token as expired this many seconds after creation. "
            "The SAT Timestamp window is 300 s; 270 absorbs clock skew."
        ),
        ge=0,
        le=300,
    )

    # Polling (poll_until_ready)
    poll_interval_seconds: float = Field(
        default=60.0,
        description="Seconds to wait between VerificaSolicitudDescarga attempts.",
        gt=0,
    )
    poll_max_attempts: int = Field(
        default=60,
        description="Maximum polling attempts before raising PollingExhaustedError.",
        ge=1,
    )
