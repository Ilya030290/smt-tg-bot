import logging
import os
import tempfile
import re
import math
import pandas as pd
import xlwings as xw
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

os.environ['XLWINGS_LICENSE_KEY'] = 'noncommercial'

from pnp_transformer import transform_pnp
from pnp_converter import convert_pnp_to_excel
from table_merger import merge_tables
from megatool_generator import (
    apply_delta_to_dataframe,
    calculate_offsets,
    generate_pnp_from_xlsm,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    try:
        with open("token.txt", "r") as f:
            TOKEN = f.read().strip()
    except FileNotFoundError:
        raise ValueError("Токен не найден")

TEMPLATE_XLSM = "template.xlsm"

# ----- Клавиатура -----
BUTTONS = {
    "start": "🏠 Главное меню",
    "create_pnp": "🛠 Преобразовать из Excel в PNP",
    "convert_altium": "🔌 Конвертировать из Altium PnP ➡ в Excel",
    "compare": "📊 Сравнить таблицы",
    "megatool": "🚀 Создать MegaTool и PNP(SMT)",
    "help": "❓ Помощь"
}
keyboard = [
    [BUTTONS["start"]],
    [BUTTONS["megatool"]],
    [BUTTONS["create_pnp"]],
    [BUTTONS["convert_altium"]],
    [BUTTONS["compare"]],
    [BUTTONS["help"]]
]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

YES_NO_KEYBOARD = [["🟢 Да", "🔴 Нет"]]
YES_NO_MARKUP = ReplyKeyboardMarkup(YES_NO_KEYBOARD, resize_keyboard=True, one_time_keyboard=True)

def make_yes_no_markup():
    return YES_NO_MARKUP

# Вспомогательная функция для скачивания файла
async def download_file(document):
    file = await document.get_file()
    suffix = os.path.splitext(document.file_name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    await file.download_to_drive(tmp.name)
    return tmp.name

# ---------- Обработчики ----------
async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == BUTTONS["start"]:
        context.user_data.clear()
        await start(update, context)
    elif text == BUTTONS["create_pnp"]:
        await pnp_start(update, context)
    elif text == BUTTONS["convert_altium"]:
        await convert_pnp_start(update, context)
    elif text == BUTTONS["compare"]:
        await compare_start(update, context)
    elif text == BUTTONS["megatool"]:
        await generate_start(update, context)
    elif text == BUTTONS["help"]:
        await help(update, context)
    else:
        await handle_gen_params_text(update, context)

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

async def pnp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 Отправьте мне Excel-файл (формат .xls или .xlsx) с тремя столбцами:\n"
        "Article name, Qty, Positions.\n"
        "Я преобразую его в PNP-формат."
    )
    context.user_data['waiting_for_excel_to_pnp'] = True

async def convert_pnp_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 Отправьте мне PnP-файл (текстовый, обычно из Altium Designer) с расширением .txt.\n"
        "Я преобразую его в Excel-формат."
    )
    context.user_data['waiting_for_pnp_to_excel'] = True

async def compare_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 Для сравнения мне понадобятся два файла.\n"
        "1️⃣ Сначала отправьте **первый файл** (Таблица1) с колонками Positions, Article name.\n"
        "2️⃣ Затем я попрошу второй файл (Таблица2) с колонками Designator, Layer, Center-X(mm), Center-Y(mm), Rotation."
    )
    context.user_data['waiting_for_first_file'] = True
    context.user_data.pop('first_file_path', None)
    context.user_data.pop('first_file_name', None)

async def generate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('waiting_for_gen_file1', None)
    context.user_data.pop('waiting_for_gen_file2', None)
    context.user_data.pop('waiting_for_gen_params', None)
    context.user_data.pop('gen_file1', None)
    context.user_data.pop('gen_file1_name', None)
    context.user_data.pop('gen_data', None)
    context.user_data.pop('gen_param_step', None)
    context.user_data.pop('df', None)

    context.user_data['waiting_for_gen_file1'] = True
    await update.message.reply_text(
        "🚀 Начинаем создание программы для SMT (полный цикл).\n"
        "Сначала мне понадобятся два файла для сравнения.\n"
        "Отправьте **первый файл** (Таблица1) с колонками:\n"
        "Positions, Article name\n"
        "(файл Excel .xls или .xlsx)"
    )

# ---------- Обработчик документов (упрощён) ----------
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name

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
                second_path = convert_pnp_to_excel(txt_path, file_name)
                os.unlink(txt_path)
            else:
                await update.message.reply_text("Пожалуйста, отправьте файл Excel (.xls/.xlsx) или текстовый PnP-файл (.txt).")
                return
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при загрузке/конвертации: {e}")
            context.user_data.pop('waiting_for_gen_file2', None)
            return

        await update.message.reply_text("⏳ Выполняю сравнение таблиц...")
        try:
            result_path = merge_tables(file1_path, second_path, file1_name)
            context.user_data['last_compare_result'] = result_path
            with open(result_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(result_path),
                    caption="📊 Результат сравнения (три листа: BottomLayer, TopLayer, DNP_List).\n"
                            "Вы можете скачать и проверить его, затем продолжим заполнять шаблон."
                )
            os.unlink(file1_path)
            os.unlink(second_path)
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
            output_path = transform_pnp(input_path, file_name)
            with open(output_path, 'rb') as f:
                await update.message.reply_document(document=f, filename=os.path.basename(output_path))
            os.unlink(input_path)
            os.unlink(output_path)
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
            output_path = convert_pnp_to_excel(input_path, file_name)
            with open(output_path, 'rb') as f:
                await update.message.reply_document(document=f, filename=os.path.basename(output_path))
            os.unlink(input_path)
            os.unlink(output_path)
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
                output_path = merge_tables(first_path, second_path, first_name)
                context.user_data['last_compare_result'] = output_path
                with open(output_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=os.path.basename(output_path),
                        caption="✅ Результат сравнения (три листа: BottomLayer, TopLayer, DNP_List)"
                    )
                os.unlink(first_path)
                os.unlink(second_path)
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

# ---------- Вспомогательные функции для генератора ----------
async def prepare_dataframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['gen_data']
    result_path = context.user_data.get('last_compare_result')
    if not result_path or not os.path.exists(result_path):
        await update.message.reply_text("❌ Ошибка: результирующая таблица не найдена.")
        context.user_data.pop('waiting_for_gen_params', None)
        context.user_data.pop('gen_data', None)
        context.user_data.pop('gen_param_step', None)
        return

    sheet_name = 'BottomLayer' if data['pcb_side'] == 'BOT' else 'TopLayer'
    df = pd.read_excel(result_path, sheet_name=sheet_name)

    if data['pcb_side'] == 'BOT':
        df['Center-X(mm)'] = -df['Center-X(mm)']

    rotation_angle = data.get('rotation_angle', 0)
    if rotation_angle != 0:
        board_x, board_y, _ = map(float, data['board_dimensions'].split(';'))
        angle_rad = math.radians(rotation_angle)
        cx = board_x / 2
        cy = board_y / 2
        x_centered = df['Center-X(mm)'] - cx
        y_centered = df['Center-Y(mm)'] - cy
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        x_rot = x_centered * cos_a - y_centered * sin_a
        y_rot = x_centered * sin_a + y_centered * cos_a
        df['Center-X(mm)'] = x_rot + cx
        df['Center-Y(mm)'] = y_rot + cy

    context.user_data['df'] = df
    data['rotation_applied'] = True
    context.user_data['gen_data'] = data
    await update.message.reply_text(
        "✅ Параметры применены. Хотите ли вы откорректировать положение платы с помощью NewX/NewY (Move Auto)? (Да/Нет):",
        reply_markup=YES_NO_MARKUP
    )
    context.user_data['gen_param_step'] = 13

# ---------- Основной обработчик диалога ----------
async def handle_gen_params_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_gen_params'):
        return

    text = update.message.text.strip()
    step = context.user_data.get('gen_param_step', 1)
    data = context.user_data.get('gen_data', {})

    logger.info(f"handle_gen_params_text: step={step}, text={text}")

    # Шаги 1–3
    if step == 1:
        data['project_name'] = text
        await update.message.reply_text("Укажите сторону платы (BOT/TOP):")
        context.user_data['gen_param_step'] = 2
    elif step == 2:
        if text.upper() not in ('BOT', 'TOP'):
            await update.message.reply_text("Пожалуйста, введите BOT или TOP:")
            return
        data['pcb_side'] = text.upper()
        await update.message.reply_text("Введите размеры платы в формате X;Y;Z (например, 200;200;1):")
        context.user_data['gen_param_step'] = 3
    elif step == 3:
        if not re.match(r'^[\d.]+;[\d.]+;[\d.]+$', text):
            await update.message.reply_text("Неверный формат. Введите три числа через точку с запятой, например 200;200;1:")
            return
        data['board_dimensions'] = text
        await update.message.reply_text("Введите количество плат на мультизаготовке в формате X;Y (например, 2;2):")
        context.user_data['gen_param_step'] = 4
        context.user_data['gen_data'] = data
        return

    # Шаг 4: мультипликация
    elif step == 4:
        if not re.match(r'^\d+;\d+$', text):
            await update.message.reply_text("Неверный формат. Введите два целых числа через точку с запятой, например 2;2:")
            return
        data['multiplication'] = text
        await update.message.reply_text(
            "Есть ли блоки с разворотом на 180 градусов?",
            reply_markup=YES_NO_MARKUP
        )
        context.user_data['gen_param_step'] = 5
        context.user_data['gen_data'] = data
        return

    # Шаг 5: ответ о разворотах
    elif step == 5:
        clean_text = text.lower().replace("🟢", "").replace("🔴", "").strip()
        if clean_text not in ('да', 'нет'):
            await update.message.reply_text("Пожалуйста, выберите Да или Нет с помощью кнопок:")
            return
        data['has_rotation'] = (clean_text == 'да')
        if data['has_rotation']:
            await update.message.reply_text("Введите номера развёрнутых блоков (через запятую, например, 3,5,7):")
            context.user_data['gen_param_step'] = 6
        else:
            await update.message.reply_text("Введите Block pitch (X;Y) в формате X;Y (например, 60;60):")
            context.user_data['gen_param_step'] = 7
        context.user_data['gen_data'] = data
        return

    # Шаг 6: номера блоков
    elif step == 6:
        try:
            numbers = [int(x.strip()) for x in text.split(',') if x.strip().isdigit()]
            if not numbers:
                raise ValueError
            data['rotated_blocks'] = numbers
        except:
            await update.message.reply_text("Неверный формат. Введите номера через запятую, например 3,5,7:")
            return

        mult_x, mult_y = map(int, data['multiplication'].split(';'))
        total_blocks = mult_x * mult_y
        if total_blocks == 2 and len(numbers) == 1:
            data['pitch_x'] = 0
            data['pitch_y'] = 0
            await ask_fiducials(update, context)
            return

        rows = set()
        cols = set()
        for n in numbers:
            if n < 1 or n > total_blocks:
                await update.message.reply_text(f"Номер блока {n} выходит за пределы (1..{total_blocks}). Повторите ввод:")
                return
            row = (n - 1) // mult_x
            col = (n - 1) % mult_x
            rows.add(row)
            cols.add(col)

        if len(rows) == 1:
            await update.message.reply_text("Введите Pitch по X (расстояние между блоками по горизонтали):")
            context.user_data['gen_param_step'] = 8
            context.user_data['pitch_axis'] = 'x'
        elif len(cols) == 1:
            await update.message.reply_text("Введите Pitch по Y (расстояние между блоками по вертикали):")
            context.user_data['gen_param_step'] = 8
            context.user_data['pitch_axis'] = 'y'
        else:
            await update.message.reply_text("Введите Pitch по X (расстояние между блоками по горизонтали):")
            context.user_data['gen_param_step'] = 8
            context.user_data['pitch_axis'] = 'x_first'
        context.user_data['gen_data'] = data
        return

    # Шаг 7: Block pitch (X;Y)
    elif step == 7:
        if not re.match(r'^[\d.]+;[\d.]+$', text):
            await update.message.reply_text("Неверный формат. Введите два числа через точку с запятой, например 60;60:")
            return
        pitch_x, pitch_y = map(float, text.split(';'))
        data['pitch_x'] = pitch_x
        data['pitch_y'] = pitch_y
        data['rotated_blocks'] = []
        await ask_fiducials(update, context)
        context.user_data['gen_data'] = data
        return

    # Шаг 8: pitch по осям
    elif step == 8:
        axis = context.user_data.get('pitch_axis')
        if axis == 'x':
            try:
                data['pitch_x'] = float(text.replace(',', '.'))
                data['pitch_y'] = 0
            except:
                await update.message.reply_text("Введите число (например, 60):")
                return
            await ask_fiducials(update, context)
        elif axis == 'y':
            try:
                data['pitch_y'] = float(text.replace(',', '.'))
                data['pitch_x'] = 0
            except:
                await update.message.reply_text("Введите число (например, 30):")
                return
            await ask_fiducials(update, context)
        elif axis == 'x_first':
            try:
                data['pitch_x'] = float(text.replace(',', '.'))
                await update.message.reply_text("Теперь введите Pitch по Y:")
                context.user_data['pitch_axis'] = 'y_second'
                context.user_data['gen_param_step'] = 8
            except:
                await update.message.reply_text("Введите число (например, 60):")
                return
        elif axis == 'y_second':
            try:
                data['pitch_y'] = float(text.replace(',', '.'))
                await ask_fiducials(update, context)
            except:
                await update.message.reply_text("Введите число (например, 30):")
                return
        context.user_data['gen_data'] = data
        return

    # Шаг 9: первая фидуциала
    elif step == 9:
        if not re.match(r'^[\d.]+;[\d.]+$', text):
            await update.message.reply_text("Неверный формат. Введите два числа через точку с запятой, например 15;4.5:")
            return
        fid_type = context.user_data.get('fiducial_type')
        if fid_type == 'bot1':
            data['fiducial_bot1'] = text
            await update.message.reply_text("Введите BOT Fiducial Mark 2 (X;Y):")
            context.user_data['fiducial_type'] = 'bot2'
            context.user_data['gen_param_step'] = 10
        elif fid_type == 'top1':
            data['fiducial_top1'] = text
            await update.message.reply_text("Введите TOP Fiducial Mark 2 (X;Y):")
            context.user_data['fiducial_type'] = 'top2'
            context.user_data['gen_param_step'] = 10
        else:
            await update.message.reply_text("Ошибка: неизвестный тип фидуциала.")
            return
        context.user_data['gen_data'] = data
        return

    # Шаг 10: вторая фидуциала + вопрос о повороте
    elif step == 10:
        if not re.match(r'^[\d.]+;[\d.]+$', text):
            await update.message.reply_text("Неверный формат. Введите два числа через точку с запятой, например 15;4.5:")
            return
        fid_type = context.user_data.get('fiducial_type')
        if fid_type == 'bot2':
            data['fiducial_bot2'] = text
        elif fid_type == 'top2':
            data['fiducial_top2'] = text
        else:
            await update.message.reply_text("Ошибка: неизвестный тип фидуциала.")
            return
        context.user_data['gen_data'] = data
        await update.message.reply_text(
            "Нужно ли повернуть плату на мультизаготовке?",
            reply_markup=YES_NO_MARKUP
        )
        context.user_data['gen_param_step'] = 11
        return

    # Шаг 11: ответ о повороте
    elif step == 11:
        clean_text = text.lower().replace("🟢", "").replace("🔴", "").strip()
        if clean_text not in ('да', 'нет'):
            await update.message.reply_text("Пожалуйста, выберите Да или Нет с помощью кнопок:")
            return
        data['need_rotation'] = (clean_text == 'да')
        if data['need_rotation']:
            await update.message.reply_text("Введите угол поворота (90, -90, 180, -180, 270, -270):")
            context.user_data['gen_param_step'] = 12
        else:
            data['rotation_angle'] = 0
            context.user_data['gen_data'] = data
            await prepare_dataframe(update, context)
        context.user_data['gen_data'] = data
        return

    # Шаг 12: угол поворота
    elif step == 12:
        try:
            angle = int(text.strip())
            if angle not in (90, -90, 180, -180, 270, -270):
                raise ValueError
            data['rotation_angle'] = angle
        except:
            await update.message.reply_text("Неверный формат. Введите 90, -90, 180, -180, 270 или -270:")
            return
        context.user_data['gen_data'] = data
        await prepare_dataframe(update, context)
        return

    # ---------- Шаги 13–21 (Move Auto + SN-LABEL) ----------
    elif step == 13:
        clean_text = text.lower().replace("🟢", "").replace("🔴", "").strip()
        if clean_text not in ('да', 'нет'):
            await update.message.reply_text("Пожалуйста, введите Да или Нет:")
            return
        if clean_text == 'нет':
            await update.message.reply_text(
                "🏷 **Вам нужно добавить наклейку SN-LABEL на плату?**",
                parse_mode="Markdown",
                reply_markup=YES_NO_MARKUP
            )
            context.user_data['gen_param_step'] = 20
            return
        else:
            await update.message.reply_text("Введите RefDes компонента для коррекции (например, C53):")
            context.user_data['gen_param_step'] = 14
            data['move_delta_x'] = 0
            data['move_delta_y'] = 0
            context.user_data['gen_data'] = data
            return

    elif step == 14:
        refdes = text.upper()
        df = context.user_data.get('df')
        if df is None or df.empty:
            await update.message.reply_text("Ошибка: данные не найдены. Начните заново.", reply_markup=reply_markup)
            context.user_data.clear()
            return
        if refdes not in df['Positions'].values:
            await update.message.reply_text(f"Компонент '{refdes}' не найден. Попробуйте ещё раз.")
            return
        data['move_refdes'] = refdes
        context.user_data['gen_data'] = data
        await update.message.reply_text(f"Введите NewX для {refdes} (число, например 12.5):")
        context.user_data['gen_param_step'] = 15
        return

    elif step == 15:
        try:
            new_x = float(text.replace(',', '.'))
            data['move_newx'] = new_x
            context.user_data['gen_data'] = data
            await update.message.reply_text(f"Введите NewY для {data['move_refdes']}:")
            context.user_data['gen_param_step'] = 16
        except:
            await update.message.reply_text("Неверный формат. Введите число (например, 12.5):")
        return

    elif step == 16:
        try:
            new_y = float(text.replace(',', '.'))
            refdes = data.get('move_refdes')
            new_x = data.get('move_newx')
            df = context.user_data.get('df')
            if df is None:
                await update.message.reply_text("Ошибка: данные не найдены. Начните заново.", reply_markup=reply_markup)
                context.user_data.clear()
                return

            old_row = df[df['Positions'] == refdes].iloc[0]
            old_x = old_row['Center-X(mm)']
            old_y = old_row['Center-Y(mm)']
            delta_x = new_x - old_x
            delta_y = new_y - old_y

            data['move_delta_x'] = data.get('move_delta_x', 0) + delta_x
            data['move_delta_y'] = data.get('move_delta_y', 0) + delta_y
            context.user_data['gen_data'] = data

            apply_delta_to_dataframe(df, delta_x, delta_y)
            context.user_data['df'] = df

            await update.message.reply_text(
                f"✅ Коррекция для {refdes} применена (NewX={new_x}, NewY={new_y}).\n"
                "Хотите ли вы скорректировать ещё один компонент?",
                reply_markup=YES_NO_MARKUP
            )
            context.user_data['gen_param_step'] = 17
        except Exception as e:
            await update.message.reply_text(f"Ошибка при вычислении дельты: {e}")
            await update.message.reply_text("Введите RefDes компонента для коррекции:")
            context.user_data['gen_param_step'] = 14
        return

    elif step == 17:
        clean_text = text.lower().replace("🟢", "").replace("🔴", "").strip()
        if clean_text not in ('да', 'нет'):
            await update.message.reply_text("Пожалуйста, введите Да или Нет:")
            return
        if clean_text == 'да':
            await update.message.reply_text("Введите RefDes компонента для коррекции:")
            context.user_data['gen_param_step'] = 14
        else:
            await update.message.reply_text(
                "🏷 **Вам нужно добавить наклейку SN-LABEL на плату?**",
                parse_mode="Markdown",
                reply_markup=YES_NO_MARKUP
            )
            context.user_data['gen_param_step'] = 20
        return

    # Шаг 20: ответ о наклейке
    elif step == 20:
        clean_text = text.lower().replace("🟢", "").replace("🔴", "").strip()
        if clean_text not in ('да', 'нет'):
            await update.message.reply_text("Пожалуйста, выберите Да или Нет с помощью кнопок:")
            return
        if clean_text == 'да':
            data['need_sn_label'] = True
            context.user_data['gen_data'] = data
            await update.message.reply_text(
                "📍 Укажите координаты для SN-LABEL.\n"
                "Числа идут строго с разделителем `;` (X;Y;Угол).\n"
                "Пример: `7.59;32.38;0` (разрешены целые и дробные числа)",
                parse_mode="Markdown"
            )
            context.user_data['gen_param_step'] = 21
        else:
            data['need_sn_label'] = False
            context.user_data['gen_data'] = data
            await save_and_send_final(update, context)
        return

    # Шаг 21: ввод координат наклейки
    elif step == 21:
        coords_input = text.strip().replace(',', '.')
        if not re.match(r'^-?\d+(\.\d+)?;-?\d+(\.\d+)?;-?\d+(\.\d+)?$', coords_input):
            await update.message.reply_text(
                "❌ Неверный формат координат!\n"
                "Введите три числа строго через точку с запятой `;`.\n"
                "Пример ввода: `7.59;32.38;0`"
            )
            return
        data['sn_label_coords'] = coords_input
        context.user_data['gen_data'] = data
        await save_and_send_final(update, context)
        return

    context.user_data['gen_data'] = data

# ---------- Сохранение и отправка финальных файлов ----------
async def save_and_send_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['gen_data']
    df = context.user_data.get('df')
    if df is None:
        await update.message.reply_text("Ошибка: данные не найдены.")
        context.user_data.clear()
        return

    if not os.path.exists(TEMPLATE_XLSM):
        await update.message.reply_text("Ошибка: файл шаблона не найден.")
        context.user_data.clear()
        return

    await update.message.reply_text("⏳ Идёт сохранение программы...")

    try:
        df = df.sort_values(by='Positions').reset_index(drop=True)

        if data.get("need_sn_label") and data.get("sn_label_coords"):
            x, y, angle = map(float, data["sn_label_coords"].split(";"))
            sn_row = {
                "Positions": "SN-LABEL",
                "Article name": "SN-LABEL",
                "Center-X(mm)": x,
                "Center-Y(mm)": y,
                "Rotation": angle,
            }
            df = pd.concat([df, pd.DataFrame([sn_row])], ignore_index=True)

        with xw.App(visible=False, add_book=False) as app:
            wb = app.books.open(TEMPLATE_XLSM)

            ws_proj = wb.sheets['Project Data']
            ws_proj.range('B1').value = data['project_name']
            ws_proj.range('B2').value = data['pcb_side']
            ws_proj.range('B3').value = data['board_dimensions']
            ws_proj.range('B4').value = data['multiplication']
            if data.get('rotated_blocks'):
                ws_proj.range('B5').value = '0;0'
            else:
                ws_proj.range('B5').value = f"{data.get('pitch_x', 0)};{data.get('pitch_y', 0)}"

            side = data['pcb_side'].upper()
            if side == 'BOT':
                ws_proj.range('B6').value = data.get('fiducial_bot1', '0;0')
                ws_proj.range('B7').value = data.get('fiducial_bot2', '0;0')
            else:
                ws_proj.range('B8').value = data.get('fiducial_top1', '0;0')
                ws_proj.range('B9').value = data.get('fiducial_top2', '0;0')

            board_x, board_y, _ = map(float, data['board_dimensions'].split(';'))
            mult_x, mult_y = map(int, data['multiplication'].split(';'))
            pitch_x = float(data.get('pitch_x', 0))
            pitch_y = float(data.get('pitch_y', 0))
            rotated = data.get('rotated_blocks', [])
            offsets = calculate_offsets(board_x, board_y, mult_x, mult_y, pitch_x, pitch_y, rotated)
            for i, offset in enumerate(offsets):
                ws_proj.range(f'B{18 + i}').value = offset

            ws_pnp = wb.sheets['PNPwizard']
            for idx, row in df.iterrows():
                row_num = idx + 2
                ws_pnp.range(f'A{row_num}').value = row['Positions']
                ws_pnp.range(f'B{row_num}').value = row['Article name']
                ws_pnp.range(f'C{row_num}').value = row['Center-X(mm)']
                ws_pnp.range(f'D{row_num}').value = row['Center-Y(mm)']
                ws_pnp.range(f'E{row_num}').value = row['Rotation']

            project_name = data.get('project_name', 'project')
            pcb_side = data.get('pcb_side', 'UNKNOWN')
            filename = f"{project_name}_{pcb_side}.xlsm"
            output_dir = tempfile.gettempdir()
            output_path = os.path.join(output_dir, filename)

            wb.save(output_path)
            wb.close()

        # Генерация .pnp
        try:
            pnp_path = generate_pnp_from_xlsm(
                output_path,
                output_dir,
                project_name,
                pcb_side
            )
            with open(pnp_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(pnp_path),
                    caption="📄 Сгенерирован PNP-файл."
                )
            os.unlink(pnp_path)
        except Exception as e:
            logger.error(f"Ошибка при генерации PNP: {e}")
            await update.message.reply_text(f"⚠️ Не удалось сгенерировать .pnp файл: {e}")

        # Отправка .xlsm
        with open(output_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=filename,
                caption="✅ Готово! Вот сгенерированная программа для SMT.\n"
                        "Данные отсортированы по RefDes, макросы и кнопки сохранены."
            )

        # Возвращаем главную клавиатуру
        await update.message.reply_text(
            "✅ Работа завершена. Можете выбрать новую команду из главного меню",
            reply_markup=reply_markup
        )

        try:
            os.unlink(output_path)
        except:
            pass

    except Exception as e:
        logger.error(f"Ошибка при сохранении: {e}")
        import traceback
        error_text = traceback.format_exc()
        await update.message.reply_text(f"❌ Ошибка: {error_text}")

    context.user_data.clear()

# ---------- Функция запроса фидуциалов ----------
async def ask_fiducials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['gen_data']
    side = data['pcb_side']
    if side == 'BOT':
        context.user_data['fiducial_type'] = 'bot1'
        context.user_data['gen_param_step'] = 9
        await update.message.reply_text("Введите BOT Fiducial Mark 1 (X;Y) (например, 15;4.5):")
    else:
        context.user_data['fiducial_type'] = 'top1'
        context.user_data['gen_param_step'] = 9
        await update.message.reply_text("Введите TOP Fiducial Mark 1 (X;Y) (например, 15;4.5):")

# ---------- Главная ----------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("create_pnp_from_excel", pnp_start))
    app.add_handler(CommandHandler("convert_from_altium_pnp_to_excel", convert_pnp_start))
    app.add_handler(CommandHandler("compare_pnp_data", compare_start))
    app.add_handler(CommandHandler("generate_megatool", generate_start))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyboard_buttons))

    print("🤖 Бот запущен и слушает сообщения... Нажми Ctrl+C для остановки.")
    app.run_polling()

if __name__ == "__main__":
    main()
