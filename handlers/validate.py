import os
import pandas as pd
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from config import reply_markup
from services.workflow import reset_workflow_state
from services.file_manager import (
    download_file,
    delete_file
)
from services.pnp_validator import (
    parse_pnp_to_dataframe,
    parse_csv_to_dataframe,
    validate_pnp_with_bom,
    generate_validation_report
)


async def run_validation_and_send_report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    bom_path: str,
    pnp_path: str,
    finish_message: str = None
):

    try:
        bom_df = await asyncio.to_thread(
            pd.read_excel,
            bom_path
        )

        if (
            'Positions' not in bom_df.columns
            or
            'Article name' not in bom_df.columns
        ):

            await update.message.reply_text(
                "❌ BOM должен содержать столбцы "
                "'Positions' и 'Article name'."
            )

            return False

        file_extension = os.path.splitext(
            pnp_path
        )[1].lower()


        if file_extension == '.pnp':

            pnp_df = await asyncio.to_thread(
                parse_pnp_to_dataframe,
                pnp_path
            )

            source_format = 'PNP'

        elif file_extension == '.csv':

            pnp_df = await asyncio.to_thread(
                parse_csv_to_dataframe,
                pnp_path
            )

            source_format = 'CSV'

        else:

            await update.message.reply_text(
                "❌ Поддерживаются только файлы "
                ".pnp и .csv."
            )

            return False


        if pnp_df.empty:

            await update.message.reply_text(
                f"❌ Не удалось извлечь данные из "
                f"{source_format}-файла."
            )

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


        with open(
            report_path,
            'rb'
        ) as f:

            await update.message.reply_document(
                document=f,
                filename='validation_report.xlsx',
                caption=(
                    "📊 Отчёт о проверке "
                    f"{source_format} по BOM.\n"
                    "Зелёным выделены совпадения, "
                    "красным — несоответствия."
                )
            )

        delete_file(bom_path)
        delete_file(pnp_path)
        delete_file(report_path)

        if finish_message:

            await update.message.reply_text(
                finish_message,
                reply_markup=reply_markup
            )

        else:

            await update.message.reply_text(
                "✅ Проверка завершена. "
                "Можете выбрать новую команду "
                "из главного меню",
                reply_markup=reply_markup
            )

        return True

    except Exception as e:

        await update.message.reply_text(
            f"❌ Ошибка при проверке: {e}"
        )

        return False


async def validate_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    reset_workflow_state(context)

    context.user_data['waiting_for_bom'] = True

    await update.message.reply_text(
        "🔍 Загрузите Excel-файл с BOM (из Odin).\n"
        "На первом листе должна быть таблица "
        "с колонками **Positions** и **Article name**.",
        parse_mode="Markdown"
    )


async def handle_bom_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    
    document = update.message.document

    file_name = document.file_name

    if not file_name.lower().endswith(
        ('.xls', '.xlsx')
    ):

        await update.message.reply_text(
            "Пожалуйста, отправьте файл Excel "
            "(.xls или .xlsx)."
        )

        return

    try:

        bom_path = await download_file(
            document
        )

        context.user_data[
            'bom_file'
        ] = bom_path

        context.user_data[
            'waiting_for_bom'
        ] = False

        context.user_data[
            'waiting_for_pnp'
        ] = True

        await update.message.reply_text(
            "✅ BOM получен.\n"
            "Теперь отправьте файл .pnp "
            "или .csv, который хотите проверить."
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Ошибка при загрузке BOM: {e}"
        )

        context.user_data.pop(
            'waiting_for_bom',
            None
        )


async def handle_pnp_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    document = update.message.document

    file_name = document.file_name


    if not file_name.lower().endswith(
        ('.pnp', '.csv')
    ):

        await update.message.reply_text(
            "Пожалуйста, отправьте файл "
            ".pnp или .csv."
        )

        return

    bom_path = context.user_data.get(
        'bom_file'
    )

    if (
        not bom_path
        or
        not os.path.exists(bom_path)
    ):

        await update.message.reply_text(
            "❌ Ошибка: BOM-файл не найден. "
            "Начните проверку заново."
        )

        context.user_data.clear()

        return

    try:
        pnp_path = await download_file(
            document
        )

        await update.message.reply_text(
            "⏳ Выполняю проверку..."
        )

        success = await run_validation_and_send_report(
            update,
            context,
            bom_path,
            pnp_path
        )

        if success:
            context.user_data.clear()

    except Exception as e:

        await update.message.reply_text(
            f"❌ Ошибка при проверке: {e}"
        )

        context.user_data.clear()
