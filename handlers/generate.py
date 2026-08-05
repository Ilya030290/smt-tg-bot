import os
import re
import math
import logging
import asyncio
import pandas as pd
from telegram import Update
from telegram.ext import ContextTypes
from config import TEMPLATE_XLSM, YES_NO_MARKUP, reply_markup
from models.project_data import ProjectData
from services.file_manager import delete_file
from services.excel.workbook_builder import build_program_files, apply_delta_to_dataframe

logger = logging.getLogger(__name__)

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
        project = ProjectData(
            project_name=data.get('project_name', ''),
            pcb_side=data.get('pcb_side', 'TOP'),
            board_dimensions=data.get('board_dimensions', '0;0;0'),
            multiplication=data.get('multiplication', '1;1'),
            rotated_blocks=data.get('rotated_blocks', []),
            pitch_x=data.get('pitch_x', 0.0),
            pitch_y=data.get('pitch_y', 0.0),
            fiducial_bot1=data.get('fiducial_bot1', '0;0'),
            fiducial_bot2=data.get('fiducial_bot2', '0;0'),
            fiducial_top1=data.get('fiducial_top1', '0;0'),
            fiducial_top2=data.get('fiducial_top2', '0;0'),
            need_sn_label=data.get('need_sn_label', False),
            sn_label_coords=data.get('sn_label_coords', ''),
            need_rotation=data.get('need_rotation', False),
            rotation_angle=data.get('rotation_angle', 0),
            move_refdes=data.get('move_refdes', ''),
            move_newx=data.get('move_newx', 0.0),
            move_newy=data.get('move_newy', 0.0),
            move_delta_x=data.get('move_delta_x', 0.0),
            move_delta_y=data.get('move_delta_y', 0.0),
        )

        xlsm_path, pnp_path = await asyncio.to_thread(
            build_program_files,
            project,
            df,
            TEMPLATE_XLSM
        )

        if pnp_path:
            context.user_data['pnp_for_validation'] = pnp_path
            with open(pnp_path, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(pnp_path),
                    caption="📄 Сгенерирован PNP-файл."
                )
        else:
            context.user_data['pnp_for_validation'] = None

        with open(xlsm_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(xlsm_path),
                caption="✅ Готово! Вот сгенерированная программа для SMT.\n"
                        "Данные отсортированы по RefDes, макросы и кнопки сохранены."
            )

        delete_file(xlsm_path)

        await update.message.reply_text(
            "❓ Вам необходимо сверить правильность заполнения партномеров и позиций вашего .pnp в соответствии с вашим BOM?",
            reply_markup=YES_NO_MARKUP
        )
        context.user_data['waiting_for_validation_answer'] = True

    except Exception as e:
        logger.error(f"Ошибка при сохранении: {e}")
        import traceback
        await update.message.reply_text(f"❌ Ошибка: {traceback.format_exc()}")

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
