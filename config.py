import os
import logging
from telegram import ReplyKeyboardMarkup

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    try:
        with open("token.txt", "r") as f:
            TOKEN = f.read().strip()
    except FileNotFoundError:
        raise ValueError("Токен не найден. Укажите TELEGRAM_TOKEN в переменных окружения или в файле token.txt")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_XLSM = os.path.join(BASE_DIR, "templates", "SMT_Template.xlsm")

if not os.path.exists(TEMPLATE_XLSM):
    TEMPLATE_XLSM = os.path.join(BASE_DIR, "template.xlsm")


BUTTONS = {
    "start": "🏠 Главное меню",
    "create_pnp": "🛠 Преобразовать из Excel в PNP",
    "convert_altium": "🔌 Конвертировать из Altium PnP ➡ в Excel",
    "compare": "📊 Сравнить таблицы",
    "megatool": "🚀 Создать MegaTool и PNP(SMT)",
    "validate": "🔍 Проверить PNP по BOM",
    "drying": "🔥 Узнать время сушки компонента",
    "help": "❓ Помощь"
}

KEYBOARD = [
    [BUTTONS["start"]],
    [BUTTONS["megatool"]],
    [BUTTONS["create_pnp"]],
    [BUTTONS["convert_altium"]],
    [BUTTONS["compare"]],
    [BUTTONS["validate"]],
    [BUTTONS["drying"]],
    [BUTTONS["help"]]
]

YES_NO_BUTTONS = [["🟢 Да", "🔴 Нет"]]

reply_markup = ReplyKeyboardMarkup(KEYBOARD, resize_keyboard=True)
YES_NO_MARKUP = ReplyKeyboardMarkup(YES_NO_BUTTONS, resize_keyboard=True, one_time_keyboard=True)

MSL_BUTTONS = [
    ["2", "2A", "3"],
    ["4", "5", "5A"]
]
MSL_KEYBOARD = ReplyKeyboardMarkup(MSL_BUTTONS, resize_keyboard=True, one_time_keyboard=True)

EXPOSURE_BUTTONS = [
    ["🔹 Больше 72 ч", "🔸 Меньше 72 ч"]
]
EXPOSURE_KEYBOARD = ReplyKeyboardMarkup(EXPOSURE_BUTTONS, resize_keyboard=True, one_time_keyboard=True)

LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOGGING_LEVEL = logging.INFO

HEALTH_PORT = int(os.environ.get("PORT", 8080))



