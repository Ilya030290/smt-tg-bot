import os
import re
import logging
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
from config import reply_markup, MSL_KEYBOARD, EXPOSURE_KEYBOARD

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
DRYING_TABLE_PATH = os.path.join(DATA_DIR, 'drying_table.xlsx')

_drying_table_cache = None

def load_drying_table():
    global _drying_table_cache
    if _drying_table_cache is not None:
        return _drying_table_cache

    if not os.path.exists(DRYING_TABLE_PATH):
        logger.error(f"Таблица сушки не найдена: {DRYING_TABLE_PATH}")
        return []

    try:
        df = pd.read_excel(DRYING_TABLE_PATH, header=None, skiprows=1)
        rows = []
        current_thickness = None

        for _, row in df.iterrows():
            thickness = row[0]
            msl = row[1]

            if pd.notna(thickness) and str(thickness).strip() != '':
                current_thickness = str(thickness).strip()

            if current_thickness and pd.notna(msl) and str(msl).strip() != '':
                rows.append({
                    'thickness_range': current_thickness,
                    'msl': str(msl).strip(),
                    'temp_125_gt72': row[2] if pd.notna(row[2]) else None,
                    'temp_125_lt72': row[3] if pd.notna(row[3]) else None,
                    'temp_90_gt72': row[4] if pd.notna(row[4]) else None,
                    'temp_90_lt72': row[5] if pd.notna(row[5]) else None,
                    'temp_40_gt72': row[6] if pd.notna(row[6]) else None,
                    'temp_40_lt72': row[7] if pd.notna(row[7]) else None,
                })

        _drying_table_cache = rows
        logger.info(f"Загружено {len(rows)} строк из таблицы сушки")
        return rows
    except Exception as e:
        logger.error(f"Ошибка загрузки таблицы сушки: {e}")
        return []

def parse_thickness(thickness_str):
    s = thickness_str.replace('mm', '').strip()
    numbers = re.findall(r'[\d.]+', s)
    if not numbers:
        return None, None

    if len(numbers) == 1:
        val = float(numbers[0])
        if '<' in s:
            return None, val
        elif '>' in s:
            return val, None
        else:
            return None, None
    elif len(numbers) == 2:
        return float(numbers[0]), float(numbers[1])
    return None, None

def find_drying_time(thickness, msl, exposure_gt72):
    table = load_drying_table()
    if not table:
        return None

    msl = str(msl).strip().upper()

    for row in table:
        if row['msl'] != msl:
            continue

        low, high = parse_thickness(row['thickness_range'])
        if low is None and high is None:
            continue

        if low is not None and thickness < low:
            continue
        if high is not None and thickness > high:
            continue

        return {
            '125': row['temp_125_gt72'] if exposure_gt72 else row['temp_125_lt72'],
            '90': row['temp_90_gt72'] if exposure_gt72 else row['temp_90_lt72'],
            '40': row['temp_40_gt72'] if exposure_gt72 else row['temp_40_lt72'],
        }
    return None

def format_drying_result(result):
    lines = []
    for temp, label in [('125', '125°C ±10°C'), ('90', '90°C ±5°C'), ('40', '40°C ±5°C')]:
        value = result.get(temp)
        if value is None or str(value).strip().lower() in ('nan', ''):
            time_str = 'Не требуется'
        else:
            time_str = str(value).strip()
        lines.append(f"🔥 **Режим сушки:** {label}")
        lines.append(f"⏱ **Время прокаливания:** {time_str}")
        lines.append("")
    return "\n".join(lines[:-1])

async def drying_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['drying_state'] = 'awaiting_thickness'
    await update.message.reply_text(
        "📏 Введите толщину корпуса компонента в мм (например, 0.7):"
    )

async def handle_drying_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('drying_state')
    text = update.message.text.strip()

    if state == 'awaiting_thickness':
        try:
            thickness = float(text.replace(',', '.'))
            if thickness <= 0:
                raise ValueError
            context.user_data['thickness'] = thickness
            context.user_data['drying_state'] = 'awaiting_msl'
            await update.message.reply_text(
                "💧 Выберите уровень MSL:",
                reply_markup=MSL_KEYBOARD
            )
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите положительное число (например, 0.7).")

    elif state == 'awaiting_msl':
        valid_msl = ['2', '2A', '3', '4', '5', '5A']
        if text not in valid_msl:
            await update.message.reply_text(
                f"❌ Пожалуйста, выберите уровень MSL из кнопок (допустимые: {', '.join(valid_msl)})",
                reply_markup=MSL_KEYBOARD
            )
            return
        context.user_data['msl'] = text
        context.user_data['drying_state'] = 'awaiting_exposure'
        await update.message.reply_text(
            "⏱ Выберите время эксплуатации после вскрытия:",
            reply_markup=EXPOSURE_KEYBOARD
        )

    elif state == 'awaiting_exposure':
        if text not in ["🔹 Больше 72 ч", "🔸 Меньше 72 ч"]:
            await update.message.reply_text(
                "❌ Пожалуйста, выберите вариант из кнопок.",
                reply_markup=EXPOSURE_KEYBOARD
            )
            return

        exposure_gt72 = (text == "🔹 Больше 72 ч")
        thickness = context.user_data.get('thickness')
        msl = context.user_data.get('msl')
        if not thickness or not msl:
            await update.message.reply_text("❌ Что-то пошло не так. Начните заново /drying_time")
            context.user_data.clear()
            return

        result = find_drying_time(thickness, msl, exposure_gt72)
        if result is None:
            await update.message.reply_text(
                "❌ Не удалось найти данные для указанных параметров. Проверьте ввод или обратитесь к администратору."
            )
            context.user_data.clear()
            await update.message.reply_text("✅ Готово! Можете выбрать новую команду.", reply_markup=reply_markup)
            return

        reply_text = format_drying_result(result)
        await update.message.reply_text(reply_text, parse_mode="Markdown")
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Готово! Можете выбрать новую команду из главного меню",
            reply_markup=reply_markup
        )

    else:
        context.user_data.clear()
        await update.message.reply_text("Начните заново с команды /drying_time")
