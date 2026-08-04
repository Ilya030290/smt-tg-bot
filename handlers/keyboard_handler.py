from telegram import Update
from telegram.ext import ContextTypes
from config import BUTTONS
from handlers.start import start, help
from handlers.create import pnp_start
from handlers.convert import convert_pnp_start
from handlers.merge import compare_start
from handlers.generate import generate_start, handle_gen_params_text

async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == BUTTONS["start"]:
        context.user_data.clear()
        await start(update, context)
    elif text == BUTTONS["create_pnp"]:
        await pnp_start(update, context)
    elif text == BUTTONS["convert_altium"]:
        await convert_pnp_start(update, context)
    elif text == BUTTONS["compare"]:
        await compare_start(update, context)
    elif text == BUTTONS["megatool"]:
        await generate_start(update, context)
    elif text == BUTTONS["help"]:
        await help(update, context)
    else:
        await handle_gen_params_text(update, context)
