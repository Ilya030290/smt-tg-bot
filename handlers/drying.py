import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import reply_markup, MSL_KEYBOARD, EXPOSURE_KEYBOARD, MSL_BUTTONS
from services.drying_service import get_drying_result


logger = logging.getLogger(__name__)


async def drying_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    context.user_data.clear()
    context.user_data['drying_state'] = (
        'awaiting_thickness'
    )

    await update.message.reply_text(
        "📏 Введите толщину корпуса компонента "
        "в мм (например, 0.7):"
    )


async def handle_drying_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    state = context.user_data.get(
        'drying_state'
    )

    text = update.message.text.strip()


    if state == 'awaiting_thickness':

        try:
            thickness = float(
                text.replace(',', '.')
            )

            if thickness <= 0:
                raise ValueError

            context.user_data['thickness'] = (
                thickness
            )

            context.user_data['drying_state'] = (
                'awaiting_msl'
            )

            await update.message.reply_text(
                "💧 Выберите уровень MSL:",
                reply_markup=MSL_KEYBOARD
            )

        except ValueError:

            await update.message.reply_text(
                "❌ Пожалуйста, введите "
                "положительное число "
                "(например, 0.7)."
            )

        return

    if state == 'awaiting_msl':

        valid_msl = [
            msl
            for row in MSL_BUTTONS
            for msl in row
        ]

        if text not in valid_msl:

            await update.message.reply_text(
                "❌ Пожалуйста, выберите уровень "
                "MSL из кнопок.\n\n"
                f"Допустимые значения: "
                f"{', '.join(valid_msl)}",
                reply_markup=MSL_KEYBOARD
            )

            return

        context.user_data['msl'] = text

        context.user_data['drying_state'] = (
            'awaiting_exposure'
        )

        await update.message.reply_text(
            "⏱ Выберите время эксплуатации "
            "после вскрытия:",
            reply_markup=EXPOSURE_KEYBOARD
        )

        return

    if state == 'awaiting_exposure':

        if text not in (
            "🔹 Больше 72 ч",
            "🔸 Меньше 72 ч"
        ):

            await update.message.reply_text(
                "❌ Пожалуйста, выберите "
                "вариант из кнопок.",
                reply_markup=EXPOSURE_KEYBOARD
            )

            return

        exposure_gt72 = (
            text == "🔹 Больше 72 ч"
        )

        thickness = context.user_data.get(
            'thickness'
        )

        msl = context.user_data.get(
            'msl'
        )

        if thickness is None or msl is None:

            await update.message.reply_text(
                "❌ Что-то пошло не так. "
                "Начните заново с команды "
                "/drying_time"
            )

            context.user_data.clear()

            return


        reply_text = get_drying_result(
            thickness=thickness,
            msl=msl,
            exposure_gt72=exposure_gt72
        )

        if reply_text is None:

            await update.message.reply_text(
                "❌ Для указанных параметров "
                "не найден подходящий диапазон "
                "в таблице сушки.\n\n"

                f"📏 Толщина корпуса: "
                f"{thickness} мм\n"

                f"💧 MSL: {msl}\n"

                f"⏱ Эксплуатация после вскрытия: "
                f"{'более 72 ч' if exposure_gt72 else 'менее 72 ч'}\n\n"

                "Проверьте указанную толщину. "
                "Возможно, она не входит в диапазоны, "
                "предусмотренные таблицей."
            )

            context.user_data.clear()

            await update.message.reply_text(
                "✅ Готово! Можете выбрать новую команду.",
                reply_markup=reply_markup
            )

            return

        await update.message.reply_text(
            reply_text,
            parse_mode="Markdown"
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ Готово! Можете выбрать новую команду "
            "из главного меню",
            reply_markup=reply_markup
        )

        return

    context.user_data.clear()

    await update.message.reply_text(
        "Начните заново с команды /drying_time"
    )
