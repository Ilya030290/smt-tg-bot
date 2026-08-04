from telegram import Update
from telegram.ext import ContextTypes
from config import BUTTONS
from handlers.start import start
from handlers.create import pnp_start
from handlers.convert import convert_pnp_start
from handlers.merge import compare_start
from handlers.help import help_command
from handlers.validate import validate_start
from handlers.generate import generate_start, handle_gen_params_text
from services.file_manager import delete_file
import os

async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if context.user_data.get('waiting_for_validation_answer'):
        clean_text = text.lower().replace('🟢', '').replace('🔴', '').strip()
        if clean_text in ('да', 'нет'):
            context.user_data.pop('waiting_for_validation_answer')
            if clean_text == 'да':
                await update.message.reply_text(
                    "📂 Отправьте Excel-файл с BOM (из Odin).\n"
                    "На первом листе должна быть таблица с колонками **Positions** и **Article name**.",
                    parse_mode="Markdown"
                )
                context.user_data['waiting_for_bom_after_generation'] = True
                return
            else:
                pnp_path = context.user_data.get('pnp_for_validation')
                if pnp_path and os.path.exists(pnp_path):
                    delete_file(pnp_path)
                context.user_data.clear()
                await update.message.reply_text(
                    "✅ Работа завершена. Можете выбрать новую команду из главного меню",
                    reply_markup=reply_markup
                )
            return
        else:
            await update.message.reply_text("Пожалуйста, выберите Да или Нет с помощью кнопок.")
            return
    
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
    elif text == BUTTONS["validate"]:
        await validate_start(update, context)     
    elif text == BUTTONS["help"]:
        await help_command(update, context)
    else:
        await handle_gen_params_text(update, context)
