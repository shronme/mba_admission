import logging

from app.core.config import settings


def configure_logging() -> None:
    """
    Basic structured-ish logging for container platforms (Railway).

    We keep it intentionally simple: timestamp + level + logger name + message.
    """

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

