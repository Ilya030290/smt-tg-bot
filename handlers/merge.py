from telegram import Update
from telegram.ext import ContextTypes
from services.workflow import reset_workflow_state 

async def compare_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    reset_workflow_state(context)
    context.user_data['waiting_for_first_file'] = True
    
    await update.message.reply_text(
        "📂 Для сравнения мне понадобятся два файла.\n"
        "1️⃣ Сначала отправьте **первый файл** (Таблица1) с колонками Positions, Article name.\n"
        "2️⃣ Затем я попрошу второй файл (Таблица2) с колонками Designator, Layer, Center-X(mm), Center-Y(mm), Rotation."
    )
    context.user_data.pop('first_file_path', None)
    context.user_data.pop('first_file_name', None)
