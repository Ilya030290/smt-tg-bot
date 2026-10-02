from telegram import Update
from telegram.ext import ContextTypes
from services.workflow import reset_workflow_state

async def pcbdoc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_workflow_state(context)
    context.user_data['waiting_for_pcbdoc'] = True
    await update.message.reply_text(
        "📎 Отправьте мне файл **.PcbDoc** из Altium Designer.\n"
        "Я конвертирую его в PnP-формат (`*_PnP.txt`) и пришлю обратно.",
        parse_mode="Markdown"
    )
