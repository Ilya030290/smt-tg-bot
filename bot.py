import os
import logging
import asyncio
import requests
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

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


logging.basicConfig(format=LOGGING_FORMAT, level=LOGGING_LEVEL)
logger = logging.getLogger(__name__)


app = Flask(__name__)


bot_app = Application.builder().token(TOKEN).build()


bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CommandHandler("create_pnp_from_excel", pnp_start))
bot_app.add_handler(CommandHandler("convert_from_altium_pnp_to_excel", convert_pnp_start))
bot_app.add_handler(CommandHandler("compare_pnp_data", compare_start))
bot_app.add_handler(CommandHandler("generate_megatool", generate_start))
bot_app.add_handler(CommandHandler("validate", validate_start))
bot_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyboard_buttons))


@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, bot_app.bot)
        
        asyncio.run(bot_app.process_update(update))
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error"}), 500


@app.route('/')
def root():
    return jsonify({"status": "Bot is alive", "message": "Ready to accept webhooks"}), 200

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/ping')
def ping():
    return "pong", 200


def set_webhook():
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        logger.warning("WEBHOOK_URL not set, webhook will not be set.")
        return
    set_webhook_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}/{TOKEN}"
    try:
        resp = requests.get(set_webhook_url)
        logger.info(f"Webhook set: {resp.json()}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

if __name__ == '__main__':
    set_webhook()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
