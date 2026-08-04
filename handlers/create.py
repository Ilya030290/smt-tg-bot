from telegram import Update
from telegram.ext import ContextTypes

async def pnp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 Отправьте мне Excel-файл (формат .xls или .xlsx) с тремя столбцами:\n"
        "Article name, Qty, Positions.\n"
        "Я преобразую его в PNP-формат."
    )
    context.user_data['waiting_for_excel_to_pnp'] = True
