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
        "❓ *Помощь* — Подробная справка по структуре исходных файлов\n\n"
        "🤖 Выберите необходимую команду на вертикальной клавиатуре ниже:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Доступные команды:\n"
        "/start – приветствие\n"
        "/help – эта справка\n"
        "/create_pnp_from_excel – преобразовать Excel-файл в PNP-формат\n"
        "/convert_from_altium_pnp_to_excel – преобразовать PnP-файл (Altium) в Excel\n"
        "/compare_pnp_data – объединить две таблицы с разделением по слоям\n"
        "/generate_megatool – полный цикл: загрузить два файла, получить результат, заполнить шаблон, применить коррекцию Move Auto (опционально) и получить .xlsm + .pnp"
    )
