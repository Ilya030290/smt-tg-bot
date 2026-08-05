import logging
import os
from aiohttp import web
from telegram import Update

from config import LOGGING_FORMAT, LOGGING_LEVEL
from app import create_application

logging.basicConfig(format=LOGGING_FORMAT, level=LOGGING_LEVEL)
logger = logging.getLogger(__name__)

def run():
    application = create_application()
    token = application.bot.token
    port = int(os.getenv("PORT", "10000"))
    webhook_url = os.getenv("WEBHOOK_URL")

    if not webhook_url:
        raise RuntimeError("WEBHOOK_URL not specified.")

    logger.info("Starting aiohttp webhook server on port %d", port)
    logger.info("Webhook URL: %s/%s", webhook_url, token)

    app = web.Application()

    # Эндпоинт для вебхука
    async def handle(request):
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
            return web.Response(status=200)
        except Exception as e:
            logger.error("Webhook error: %s", e, exc_info=True)
            return web.Response(status=500)

    app.router.add_post(f'/{token}', handle)

    # Эндпоинты для health check (Render будет проверять / и /health)
    async def health(request):
        return web.Response(text="OK", status=200)

    app.router.add_get('/health', health)
    app.router.add_get('/', health)

    # Запуск сервера (блокирует выполнение)
    web.run_app(app, host='0.0.0.0', port=port)
