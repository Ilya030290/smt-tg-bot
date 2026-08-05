import os
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from services.file_manager import download_file, delete_file
from services.excel.transformer import transform_pnp
from services.excel.converter import convert_pnp_to_excel
from services.excel.merger import merge_tables

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name

    # Отдельная команда: ожидание BOM
    if context.user_data.get('waiting_for_bom'):
        from handlers.validate import handle_bom_file
        await handle_bom_file(update, context)
        return

    # Отдельная команда: ожидание PNP
    if context.user_data.get('waiting_for_pnp'):
        from handlers.validate import handle_pnp_file
        await handle_pnp_file(update, context)
        return

    # После генерации: ожидание BOM для проверки
    if context.user_data.get('waiting_for_bom_after_generation'):
        if not file_name.endswith(('.xls', '.xlsx')):
            await update.message.reply_text("Пожалуйста, отправьте файл Excel (.xls или .xlsx).")
            return
        try:
            bom_path = await download_file(document)
            pnp_path = context.user_data.get('pnp_for_validation')
            if not pnp_path or not os.path.exists(pnp_path):
                await update.message.reply_text("❌ Ошибка: файл .pnp не найден. Попробуйте сгенерировать заново.")
                context.user_data.clear()
                return

            await update.message.reply_text("⏳ Выполняю проверку...")
            from handlers.validate import run_validation_and_send_report
            success = await run_validation_and_send_report(
                update, context, bom_path, pnp_path,
                finish_message="✅ Работа завершена. Можете выбрать новую команду из главного меню"
            )
            if success:
                context.user_data.clear()
            else:
                context.user_data.clear()
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при проверке: {e}")
            context.user_data.clear()
        return
    
    # Генератор: первый файл
    if context.user_data.get('waiting_for_gen_file1'):
        if not file_name.endswith(('.xls', '.xlsx')):
            await update.message.reply_text("Пожалуйста, отправьте первый файл Excel (.xls или .xlsx).")
            return
        try:
            tmp_path = await download_file(document)
            context.user_data['gen_file1'] = tmp_path
            context.user_data['gen_file1_name'] = file_name
            context.user_data.pop('waiting_for_gen_file1')
            context.user_data['waiting_for_gen_file2'] = True
            await update.message.reply_text(
                "✅ Первый файл получен.\n"
                "Теперь отправьте **второй файл** (Таблица2) – это может быть Excel-файл с колонками Designator, Layer, Center-X(mm), Center-Y(mm), Rotation\n"
                "ИЛИ текстовый PnP-файл из Altium Designer (.txt), который я сконвертирую в Excel."
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при загрузке файла: {e}")
            context.user_data.pop('waiting_for_gen_file1', None)
        return

    # Генератор: второй файл
    if context.user_data.get('waiting_for_gen_file2'):
        file1_path = context.user_data.get('gen_file1')
        file1_name = context.user_data.get('gen_file1_name')
        if not file1_path:
            await update.message.reply_text("Ошибка: первый файл не найден. Начните заново с /generate_megatool.")
            context.user_data.pop('waiting_for_gen_file2', None)
            return

        try:
            if file_name.endswith(('.xls', '.xlsx')):
                second_path = await download_file(document)
            elif file_name.endswith('.txt'):
                txt_path = await download_file(document)
                await update.message.reply_text("⏳ Конвертирую PnP-файл в Excel...")
                second_path = await asyncio.to_thread(
                    convert_pnp_to_excel,
                    txt_path,
                    file_name
                )
                delete_file(txt_path)
            else:
                await update.message.reply_text("Пожалуйста, отправьте файл Excel (.xls/.xlsx) или текстовый PnP-файл (.txt).")
                return
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при загрузке/конвертации: {e}")
            context.user_data.pop('waiting_for_gen_file2', None)
            return

        await update.message.reply_text("⏳ Выполняю сравнение таблиц...")
        try:
            result_path =await asyncio.to_thread(
                merge_tables,
                file1_path,
                second_path,
                file1_name
            ) 
            context.user_data['last_compare_result'] = result_path
            with open(result_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(result_path),
                    caption="📊 Результат сравнения (три листа: BottomLayer, TopLayer, DNP_List).\n"
                            "Вы можете скачать и проверить его, затем продолжим заполнять шаблон."
                )
            delete_file(file1_path)
            delete_file(second_path)
            context.user_data.pop('gen_file1', None)
            context.user_data.pop('gen_file1_name', None)
            context.user_data.pop('waiting_for_gen_file2')

            context.user_data['waiting_for_gen_params'] = True
            context.user_data['gen_data'] = {}
            context.user_data['gen_param_step'] = 1
            await update.message.reply_text("✅ Сравнение выполнено. Теперь введите название проекта:")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при сравнении: {e}")
            context.user_data.pop('waiting_for_gen_file2', None)
        return

    # Обработка /create_pnp_from_excel
    if context.user_data.get('waiting_for_excel_to_pnp', False):
        if not file_name.endswith(('.xls', '.xlsx')):
            await update.message.reply_text("Пожалуйста, отправьте файл Excel.")
            return
        await update.message.reply_text("⏳ Обрабатываю...")
        try:
            input_path = await download_file(document)
            output_path = await asyncio.to_thread(
                transform_pnp,
                input_path,
                file_name
            )
            with open(output_path, 'rb') as f:
                await update.message.reply_document(document=f, filename=os.path.basename(output_path))
            delete_file(input_path)
            delete_file(output_path)
            context.user_data['waiting_for_excel_to_pnp'] = False
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
            context.user_data['waiting_for_excel_to_pnp'] = False
        return

    # Обработка /convert_from_altium_pnp_to_excel
    if context.user_data.get('waiting_for_pnp_to_excel', False):
        if not file_name.endswith('.txt'):
            await update.message.reply_text("Пожалуйста, отправьте текстовый файл .txt.")
            return
        await update.message.reply_text("⏳ Обрабатываю...")
        try:
            input_path = await download_file(document)
            output_path = await asyncio.to_thread(
                convert_pnp_to_excel,
                input_path,
                file_name
            )
            with open(output_path, 'rb') as f:
                await update.message.reply_document(document=f, filename=os.path.basename(output_path))
            delete_file(input_path)
            delete_file(output_path)
            context.user_data['waiting_for_pnp_to_excel'] = False
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
            context.user_data['waiting_for_pnp_to_excel'] = False
        return

    # Обработка /compare_pnp_data
    if context.user_data.get('waiting_for_first_file', False) or context.user_data.get('waiting_for_second_file', False):
        if not file_name.endswith(('.xls', '.xlsx')):
            await update.message.reply_text("Пожалуйста, отправьте файл Excel.")
            return

        if context.user_data.get('waiting_for_first_file', False):
            try:
                tmp_path = await download_file(document)
                context.user_data['first_file_path'] = tmp_path
                context.user_data['first_file_name'] = file_name
                context.user_data['waiting_for_first_file'] = False
                context.user_data['waiting_for_second_file'] = True
                await update.message.reply_text("✅ Первый файл получен. Теперь отправьте второй файл (Таблица2).")
            except Exception as e:
                await update.message.reply_text(f"Ошибка: {e}")
                context.user_data.pop('waiting_for_first_file', None)
            return

        if context.user_data.get('waiting_for_second_file', False):
            first_path = context.user_data.get('first_file_path')
            first_name = context.user_data.get('first_file_name')
            if not first_path:
                await update.message.reply_text("Ошибка: первый файл не найден. Начните заново.")
                context.user_data.pop('waiting_for_second_file', None)
                return

            try:
                second_path = await download_file(document)
                await update.message.reply_text("⏳ Выполняю сравнение...")
                output_path = await asyncio.to_thread(
                    merge_tables,
                    first_path,
                    second_path,
                    first_name
                ) 
                context.user_data['last_compare_result'] = output_path
                with open(output_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=os.path.basename(output_path),
                        caption="✅ Результат сравнения (три листа: BottomLayer, TopLayer, DNP_List)"
                    )
                delete_file(first_path)
                delete_file(second_path)
                context.user_data.pop('waiting_for_second_file', None)
                context.user_data.pop('first_file_path', None)
                context.user_data.pop('first_file_name', None)
            except Exception as e:
                await update.message.reply_text(f"Ошибка: {e}")
                context.user_data.pop('waiting_for_second_file', None)
                context.user_data.pop('first_file_path', None)
            return

    await update.message.reply_text(
        "Я не ожидаю файл. Используйте кнопки или команды:\n"
        "/create_pnp_from_excel\n"
        "/convert_from_altium_pnp_to_excel\n"
        "/compare_pnp_data\n"
        "/generate_megatool"
    )
