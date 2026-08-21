import os
import re
import logging

import pandas as pd


logger = logging.getLogger(__name__)


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data'
)

DRYING_TABLE_PATH = os.path.join(
    DATA_DIR,
    'drying_table.xlsx'
)


_drying_table_cache = None


def load_drying_table():
    global _drying_table_cache

    if _drying_table_cache is not None:
        return _drying_table_cache

    if not os.path.exists(DRYING_TABLE_PATH):
        logger.error(
            f"Таблица сушки не найдена: {DRYING_TABLE_PATH}"
        )
        return []

    try:
        df = pd.read_excel(
            DRYING_TABLE_PATH,
            header=None,
            skiprows=1
        )

        rows = []
        current_thickness = None

        for _, row in df.iterrows():

            thickness = row[0]
            msl = row[1]
            if (
                pd.notna(thickness)
                and str(thickness).strip() != ''
            ):
                current_thickness = str(thickness).strip()
            if (
                current_thickness
                and pd.notna(msl)
                and str(msl).strip() != ''
            ):
                rows.append({
                    'thickness_range': current_thickness,
                    'msl': str(msl).strip(),

                    'temp_125_gt72':
                        row[2] if pd.notna(row[2]) else None,

                    'temp_125_lt72':
                        row[3] if pd.notna(row[3]) else None,

                    'temp_90_gt72':
                        row[4] if pd.notna(row[4]) else None,

                    'temp_90_lt72':
                        row[5] if pd.notna(row[5]) else None,

                    'temp_40_gt72':
                        row[6] if pd.notna(row[6]) else None,

                    'temp_40_lt72':
                        row[7] if pd.notna(row[7]) else None,
                })

        _drying_table_cache = rows

        logger.info(
            f"Загружено {len(rows)} строк из таблицы сушки"
        )

        return rows

    except Exception as e:
        logger.exception(
            f"Ошибка загрузки таблицы сушки: {e}"
        )
        return []


def parse_thickness(thickness_str):
    if thickness_str is None:
        return None, None

    s = str(thickness_str).strip().lower()

    s = s.replace('mm', '')
    s = s.replace('–', '-')
    s = s.replace('—', '-')
    s = s.replace(' ', '')

    numbers = re.findall(
        r'\d+(?:[.,]\d+)?',
        s
    )

    if not numbers:
        return None, None

    if s.startswith('<'):
        high = float(
            numbers[0].replace(',', '.')
        )
        return None, high

    if s.startswith('>'):
        low = float(
            numbers[0].replace(',', '.')
        )
        return low, None

    if len(numbers) == 2:
        low = float(
            numbers[0].replace(',', '.')
        )
        high = float(
            numbers[1].replace(',', '.')
        )
        return low, high

    if len(numbers) == 1:
        value = float(
            numbers[0].replace(',', '.')
        )
        return value, value

    return None, None


def find_drying_time(
    thickness: float,
    msl: str,
    exposure_gt72: bool
):

    table = load_drying_table()

    if not table:
        return None

    msl = str(msl).strip().upper()

    for row in table:

        row_msl = str(
            row['msl']
        ).strip().upper()

        if row_msl != msl:
            continue

        low, high = parse_thickness(
            row['thickness_range']
        )

        if low is None and high is None:
            continue

        if low is not None and thickness < low:
            continue
        
        if high is not None and thickness > high:
            continue

        return {
            '125': (
                row['temp_125_gt72']
                if exposure_gt72
                else row['temp_125_lt72']
            ),

            '90': (
                row['temp_90_gt72']
                if exposure_gt72
                else row['temp_90_lt72']
            ),

            '40': (
                row['temp_40_gt72']
                if exposure_gt72
                else row['temp_40_lt72']
            ),
        }

    return None


def format_drying_result(result):

    lines = []

    temperatures = [
        ('125', '125°C ±10°C'),
        ('90', '90°C ±5°C'),
        ('40', '40°C ±5°C'),
    ]

    for temp, label in temperatures:

        value = result.get(temp)

        if (
            value is None
            or str(value).strip().lower() in ('nan', '')
        ):
            time_str = 'Не требуется'
        else:
            time_str = str(value).strip()

        lines.append(
            f"🔥 **Режим сушки:** {label}"
        )

        lines.append(
            f"⏱ **Время прокаливания:** {time_str}"
        )

        lines.append("")

    return "\n".join(lines[:-1])


def get_drying_result(
    thickness: float,
    msl: str,
    exposure_gt72: bool
):

    result = find_drying_time(
        thickness=thickness,
        msl=msl,
        exposure_gt72=exposure_gt72
    )

    if result is None:
        return None

    return format_drying_result(result)
