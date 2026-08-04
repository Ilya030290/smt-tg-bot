import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import TOKEN, LOGGING_FORMAT, LOGGING_LEVEL
from handlers.start import start, help
from handlers.create import pnp_start
from handlers.convert import convert_pnp_start
from handlers.merge import compare_start
from handlers.generate import generate_start
from handlers.keyboard_handler import handle_keyboard_buttons
from handlers.documents import handle_document

# Настройка логирования
logging.basicConfig(format=LOGGING_FORMAT, level=LOGGING_LEVEL)
logger = logging.getLogger(__name__)

# Health-сервер
from utils.http_server import start_health_thread
start_health_thread()

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("create_pnp_from_excel", pnp_start))
    app.add_handler(CommandHandler("convert_from_altium_pnp_to_excel", convert_pnp_start))
    app.add_handler(CommandHandler("compare_pnp_data", compare_start))
    app.add_handler(CommandHandler("generate_megatool", generate_start))
    
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyboard_buttons))
    
    print("🤖 Бот запущен и слушает сообщения... Нажми Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
