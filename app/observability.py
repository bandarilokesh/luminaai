"""Langfuse setup. Import this module before any traced code so the client is configured.

When LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are blank, tracing is disabled and every
`@observe` decorator and the OpenAI wrapper become no-ops.
"""
from langfuse import Langfuse, get_client, observe  # noqa: F401  (re-exported)

from app.config import settings
from app.logger import logger

TRACING_ENABLED = bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)

# Placeholder keys keep the SDK quiet when tracing is off; nothing is sent in that case.
langfuse = Langfuse(
    public_key=settings.LANGFUSE_PUBLIC_KEY or "tracing-disabled",
    secret_key=settings.LANGFUSE_SECRET_KEY or "tracing-disabled",
    base_url=settings.LANGFUSE_BASE_URL,
    tracing_enabled=TRACING_ENABLED,
)

if TRACING_ENABLED:
    logger.info(f"Langfuse tracing enabled ({settings.LANGFUSE_BASE_URL})")
else:
    logger.info("Langfuse tracing disabled (no LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY)")


def langfuse_status() -> str:
    if not TRACING_ENABLED:
        return "Disabled"
    try:
        return "Connected" if langfuse.auth_check() else "Auth failed"
    except Exception as e:
        logger.warning(f"Langfuse auth check failed: {e}")
        return "Unreachable"
