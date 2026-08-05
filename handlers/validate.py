import os
import pandas as pd
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from config import reply_markup
from services.file_manager import download_file, delete_file
from services.pnp_validator import parse_pnp_to_dataframe, validate_pnp_with_bom, generate_validation_report

async def run_validation_and_send_report(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                          bom_path: str, pnp_path: str,
                                          finish_message: str = None):
    """
    Выполняет проверку .pnp по BOM и отправляет отчёт.
    После отправки удаляет временные файлы.
    Если finish_message задан, отправляет его после отчёта.
    Возвращает True при успехе, False при ошибке.
    """
    try:
        bom_df = await asyncio.to_thread(
            pd.read_excel,
            bom_path
        ) 
        if 'Positions' not in bom_df.columns or 'Article name' not in bom_df.columns:
            await update.message.reply_text("❌ BOM должен содержать столбцы 'Positions' и 'Article name'.")
            return False

        pnp_df = await asyncio.to_thread(
            parse_pnp_to_dataframe,
            pnp_path
        )
        if pnp_df.empty:
            await update.message.reply_text("❌ Не удалось извлечь данные из .pnp. Проверьте формат файла.")
            return False

        result_df = await asyncio.to_thread(
            validate_pnp_with_bom,
            pnp_df,
            bom_df
        ) 
        report_path = await asyncio.to_thread(
            generate_validation_report,
            result_df
        ) 

        with open(report_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename='validation_report.xlsx',
                caption="📊 Отчёт о проверке PNP по BOM.\n"
                        "Зелёным выделены совпадения, красным — несоответствия."
            )

        # Удаляем временные файлы
        delete_file(bom_path)
        delete_file(pnp_path)
        delete_file(report_path)

        if finish_message:
            await update.message.reply_text(finish_message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(
                "✅ Проверка завершена. Можете выбрать новую команду из главного меню",
                reply_markup=reply_markup
            )
        return True
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при проверке: {e}")
        return False

async def validate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало отдельной проверки: запрос BOM-файла."""
    context.user_data.clear()
    context.user_data['waiting_for_bom'] = True
    await update.message.reply_text(
        "🔍 Загрузите Excel-файл с BOM (из Odin).\n"
        "На первом листе должна быть таблица с колонками **Positions** и **Article name**.",
        parse_mode="Markdown"
    )

async def handle_bom_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка BOM для отдельной проверки."""
    document = update.message.document
    file_name = document.file_name
    if not file_name.endswith(('.xls', '.xlsx')):
        await update.message.reply_text("Пожалуйста, отправьте файл Excel (.xls или .xlsx).")
        return
    try:
        bom_path = await download_file(document)
        context.user_data['bom_file'] = bom_path
        context.user_data['waiting_for_bom'] = False
        context.user_data['waiting_for_pnp'] = True
        await update.message.reply_text(
            "✅ BOM получен. Теперь отправьте .pnp файл, который хотите проверить."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при загрузке BOM: {e}")
        context.user_data.pop('waiting_for_bom', None)

async def handle_pnp_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка .pnp для отдельной проверки."""
    document = update.message.document
    file_name = document.file_name
    if not file_name.endswith('.pnp'):
        await update.message.reply_text("Пожалуйста, отправьте файл .pnp.")
        return

    bom_path = context.user_data.get('bom_file')
    if not bom_path or not os.path.exists(bom_path):
        await update.message.reply_text("❌ Ошибка: BOM-файл не найден. Начните проверку заново.")
        context.user_data.clear()
        return

    try:
        pnp_path = await download_file(document)
        await update.message.reply_text("⏳ Выполняю проверку...")
        success = await run_validation_and_send_report(update, context, bom_path, pnp_path)
        if success:
            context.user_data.clear()
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при проверке: {e}")
        context.user_data.clear()
