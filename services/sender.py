from telegram import Update, ReplyKeybfrom telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

async def reply_text(update: Update, text: str, parse_mode: str = None, reply_markup=None):
    """Отправляет текстовое сообщение."""
    await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)

async def reply_document(update: Update, file_path: str, filename: str = None, caption: str = ""):
    """Отправляет файл."""
    with open(file_path, 'rb') as f:
        await update.message.reply_document(document=f, filename=filename or os.path.basename(file_path), caption=caption)
