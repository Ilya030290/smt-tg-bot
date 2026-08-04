from telegram import Update
from telegram.ext import ContextTypes
from config import reply_markup

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help и кнопки Помощь."""
    await update.message.reply_text(
        "📌 Доступные команды и функции:\n\n"
        "🏠 /start – главное меню\n"
        "🚀 /generate_megatool – полный цикл: загрузить два файла, получить .xlsm + .pnp\n"
        "🛠 /create_pnp_from_excel – преобразовать Excel-файл в PNP-формат\n"
        "🔌 /convert_from_altium_pnp_to_excel – конвертировать PnP-файл (Altium) в Excel\n"
        "📊 /compare_pnp_data – объединить две таблицы с разделением по слоям\n"
        "🔍 /validate – проверить .pnp файл по BOM (Excel-таблице с Positions и Article name)\n"
        "❓ /help – эта справка\n\n"
        "💡 Подробности по каждому инструменту доступны в процессе работы.\n"
        "Если возникнут вопросы – обращайтесь.",
        reply_markup=reply_markup
    )
