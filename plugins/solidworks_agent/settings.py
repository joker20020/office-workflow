"""Configuration for the SolidWorks subagent plugin."""

import math
import os

DEFAULT_EXECUTION_TIMEOUT_SECONDS = 600.0
EXECUTION_TIMEOUT_ENV = "SOLIDWORKS_MCP_TIMEOUT_SECONDS"


def execution_timeout_seconds() -> float:
    """Return a positive configured MCP timeout, or the safe default."""
    raw = os.environ.get(EXECUTION_TIMEOUT_ENV)
    if raw is None:
        return DEFAULT_EXECUTION_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_EXECUTION_TIMEOUT_SECONDS
    if not math.isfinite(value) or value <= 0:
        return DEFAULT_EXECUTION_TIMEOUT_SECONDS
    return value
