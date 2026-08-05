import logging
import os

from config import (
    LOGGING_FORMAT,
    LOGGING_LEVEL,
)

from app import create_application


logging.basicConfig(
    format=LOGGING_FORMAT,
    level=LOGGING_LEVEL,
)

logger = logging.getLogger(__name__)


def run():

    application = create_application()

    port = int(
        os.getenv(
            "PORT",
            "10000"
        )
    )

    webhook_url = os.getenv("WEBHOOK_URL")

    if not webhook_url:
        raise RuntimeError(
            "WEBHOOK_URL not specified."
        )

    logger.info(
        "Starting webhook..."
    )

    logger.info(
        "Webhook URL: %s",
        webhook_url
    )

    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=application.bot.token,
        webhook_url=f"{webhook_url}/{application.bot.token}",
        allowed_updates=None,
        drop_pending_updates=False,
    )
