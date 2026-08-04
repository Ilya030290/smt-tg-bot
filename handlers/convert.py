from telegram import Update
from telegram.ext import ContextTypes

async def convert_pnp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 Отправьте мне PnP-файл (текстовый, обычно из Altium Designer) с расширением .txt.\n"
        "Я преобразую его в Excel-формат."
    )
    context.user_data['waiting_for_pnp_to_excel'] = True
