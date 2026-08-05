import logging
import os
import asyncio
from aiohttp import web
from telegram import Update
from config import LOGGING_FORMAT, LOGGING_LEVEL
from app import create_application

logging.basicConfig(format=LOGGING_FORMAT, level=LOGGING_LEVEL)
logger = logging.getLogger(__name__)

async def main():
    application = create_application()
    token = application.bot.token
    port = int(os.getenv("PORT", "10000"))
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if not webhook_url:
        raise RuntimeError("WEBHOOK_URL not specified.")

    await application.initialize()
    await application.start()
    
    await application.bot.set_webhook(url=f"{webhook_url}/{token}")
    logger.info("Webhook set to: %s/%s", webhook_url, token)

    app = web.Application()

    async def handle(request):
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
            return web.Response(status=200)
        except Exception as e:
            logger.error("Webhook error: %s", e, exc_info=True)
            return web.Response(status=500)

    async def health(request):
        return web.Response(text="OK", status=200)

    app.router.add_post(f'/{token}', handle)
    app.router.add_get('/health', health)
    app.router.add_get('/', health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    await site.start()
    logger.info("Server started on port %d", port)

    try:
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Stopping server...")
    finally:
        await application.bot.delete_webhook()
        await application.stop()
        await application.shutdown()
        await runner.cleanup()
        logger.info("Server stopped cleanly.")

def run():
    asyncio.run(main())

if __name__ == "__main__":
    run()
