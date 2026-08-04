from telegram import Update
from telegram.ext import ContextTypes
from config import BUTTONS, reply_markup

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.effective_message.reply_text(
        f"Привет, {update.effective_user.first_name}! 🛠️\n\n"
        "Я специализированный бот для подготовки программ SMT и работы с PNP-файлами.\n"
        "Все макросы, графики и кнопки в ваших итоговых документах полностью сохраняются.\n\n"
        "📌 **Доступные инструменты управления:**\n\n"
        "🚀 *Создать MegaTool и PNP(SMT)* — Полный цикл подготовки программы (.xlsm + .pnp)\n"
        "🛠 *Преобразовать из Excel в PNP* — Быстрое преобразование таблицы в PNP-формат\n"
        "🔌 *Конвертировать из Altium PnP ➡ в Excel* — Импорт данных из Altium Designer (.txt)\n"
        "📊 *Сравнить таблицы* — Объединение и разделение списков по слоям\n"
        "🔍 *Проверить PNP по BOM* — Сравнение необходимого .pnp с вашей BOM-таблицей\n"
        "❓ *Помощь* — Подробная справка по структуре исходных файлов\n\n"
        "🤖 Выберите необходимую команду на вертикальной клавиатуре ниже:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Помощь'"""
    from handlers.help import help_command
    await help_command(update, context)
