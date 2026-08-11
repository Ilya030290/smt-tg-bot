from telegram import Update
from telegram.ext import ContextTypes
from services.workflow import reset_workflow_state

async def convert_pnp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    reset_workflow_state(context)
    context.user_data['waiting_for_pnp_to_excel'] = True
    
    await update.message.reply_text(
        "📂 Отправьте мне PnP-файл (текстовый, обычно из Altium Designer) с расширением .txt.\n"
        "Я преобразую его в Excel-формат."
    )
