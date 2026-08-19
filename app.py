from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import TOKEN

from handlers.start import start
from handlers.help import help_command
from handlers.create import pnp_start
from handlers.convert import convert_pnp_start
from handlers.merge import compare_start
from handlers.generate import generate_start
from handlers.validate import validate_start
from handlers.keyboard_handler import handle_keyboard_buttons
from handlers.documents import handle_document
from handlers.drying import drying_start

def create_application() -> Application:

    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("create_pnp_from_excel", pnp_start))
    application.add_handler(CommandHandler("convert_from_altium_pnp_to_excel", convert_pnp_start))
    application.add_handler(CommandHandler("compare_pnp_data", compare_start))
    application.add_handler(CommandHandler("generate_megatool", generate_start))
    application.add_handler(CommandHandler("validate", validate_start))
    application.add_handler(CommandHandler("drying_time", drying_start))
    
    application.add_handler(
        MessageHandler(
            filters.Document.ALL,
            handle_document
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_keyboard_buttons
        )
    )

    return application
