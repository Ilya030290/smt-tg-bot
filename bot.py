import os
import logging
import asyncio
import traceback

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import TOKEN, LOGGING_FORMAT, LOGGING_LEVEL

from handlers.start import start
from handlers.help import help_command
from handlers.create import pnp_start
from handlers.convert import convert_pnp_start
from handlers.merge import compare_start
from handlers.generate import generate_start
from handlers.validate import validate_start
from handlers.keyboard_handler import handle_keyboard_buttons
from handlers.documents import handle_document


logging.basicConfig(
    format=LOGGING_FORMAT,
    level=LOGGING_LEVEL
)

logger = logging.getLogger(__name__)


app = Flask(__name__)


application = Application.builder().token(TOKEN).build()


application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("create_pnp_from_excel", pnp_start))
application.add_handler(CommandHandler("convert_from_altium_pnp_to_excel", convert_pnp_start))
application.add_handler(CommandHandler("compare_pnp_data", compare_start))
application.add_handler(CommandHandler("generate_megatool", generate_start))
application.add_handler(CommandHandler("validate", validate_start))

application.add_handler(
    MessageHandler(filters.Document.ALL, handle_document)
)

application.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND,
                   handle_keyboard_buttons)
)


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


async def startup():
    await application.initialize()
    await application.start()
    logger.info("Telegram Application initialized")
    
loop.run_until_complete(startup())    
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if WEBHOOK_URL:
    loop.run_until_complete(
        application.bot.set_webhook(
            url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    )
    logger.info("Webhook установлен.")


@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():

    try:
        data = request.get_json(force=True)

        logger.info(
            "Update %s from chat %s",
            data.get("update_id"),
            data.get("message", {}).get("chat", {}).get("id")
        )

        update = Update.de_json(data, application.bot)

        loop.run_until_complete(
            application.process_update(update)
        )

        return "OK", 200

    except Exception:

        logger.error(traceback.format_exc())

        return "ERROR", 500


@app.route("/")
def index():
    return "Bot is running"


@app.route("/health")
def health():
    return "OK"


@app.route("/ping")
def ping():
    return "pong"


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
