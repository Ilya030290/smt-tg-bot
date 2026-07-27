import os
import re
import tempfile
import pandas as pd
import chardet


# Вспомогательные функции
def detect_delimiter(line):
    if '!' in line:
        return '!'
    if '\t' in line:
        return '\t'
    return None

def split_line(line, delimiter):
    if delimiter == '!':
        parts = [p.strip() for p in line.split('!')]
        return [p for p in parts if p]
    elif delimiter == '\t':
        return [p.strip() for p in line.split('\t')]
    else:
        return split_preserving_quotes(line)

def split_preserving_quotes(line):
    parts = re.findall(r'(?:[^\s"]+|"[^"]*")+', line)
    return [p.strip() for p in parts]

def safe_read_file(file_path):
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(100000)
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding')
            confidence = detected.get('confidence', 0)
            if confidence < 0.5 or encoding is None:
                encoding = None
    except:
        encoding = None

    encodings_to_try = []
    if encoding:
        encodings_to_try.append(encoding)
    encodings_to_try.extend(['utf-8', 'latin-1', 'cp1252', 'cp1251', 'iso-8859-1'])
    seen = set()
    encodings_to_try = [enc for enc in encodings_to_try if not (enc in seen or seen.add(enc))]

    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc, errors='replace') as f:
                lines = f.readlines()
            return lines
        except:
            continue

    with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
        lines = f.readlines()
    return lines

def normalize_layer_from_mirror(value):
    if pd.isna(value) or value == '':
        return 'TopLayer'
    s = str(value).strip().lower()
    if s in ('m', 'mirror', '1', 'true', 'yes'):
        return 'BottomLayer'
    return 'TopLayer'

def normalize_layer_general(value):
    if pd.isna(value) or value == '':
        return 'TopLayer'
    s = str(value).strip().lower()
    bottom_keywords = ('bottomlayer', 'bottom', 'b', 'mirror', 'm', '1', 'true', 'yes')
    if s in bottom_keywords:
        return 'BottomLayer'
    return 'TopLayer'

def convert_units(value, unit_is_mil):
    if not unit_is_mil:
        return value
    try:
        if isinstance(value, str) and any(c.isalpha() or c in '()"\'<>' for c in value):
            return value
        num = float(str(value).replace(',', '.'))
        return num * 0.0254
    except:
        return value

def safe_convert(series, is_mil=False):
    converted = []
    for val in series:
        try:
            if is_mil:
                res = convert_units(val, True)
            else:
                if str(val).replace(',', '').replace('.', '').isdigit():
                    res = float(str(val).replace(',', '.'))
                else:
                    res = val
            converted.append(res)
        except:
            converted.append(val)
    return converted

def find_column_by_keywords(df, keywords):
    df_lower_cols = {col: col.lower() for col in df.columns}
    for kw in keywords:
        kw_lower = kw.lower()
        for orig_col, lower_col in df_lower_cols.items():
            if kw_lower in lower_col:
                return orig_col
    return None

def convert_pnp_to_excel(input_path, original_filename):
    """Преобразует PnP-файл (текстовый) в Excel."""
    try:
        lines = safe_read_file(input_path)
    except Exception as e:
        raise RuntimeError(f"Ошибка при чтении файла: {e}")

    delimiter = None
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            if '!' in stripped:
                delimiter = '!'
                break
            if '\t' in stripped:
                delimiter = '\t'
                break
    if delimiter is None:
        for line in lines:
            if any(kw in line.lower() for kw in ['refdes', 'designator', 'symbol_x']):
                if '!' in line:
                    delimiter = '!'
                    break
                if '\t' in line:
                    delimiter = '\t'
                    break
    if delimiter is None:
        delimiter = ' '

    header_line = None
    header_index = -1
    keyword_groups = {
        'designator': ['designator', 'refdes'],
        'center_x': ['center-x', 'symbol_x'],
        'center_y': ['center-y', 'symbol_y']
    }
    for i, line in enumerate(lines):
        line_lower = line.lower()
        has_des = any(kw in line_lower for kw in keyword_groups['designator'])
        has_x = any(kw in line_lower for kw in keyword_groups['center_x'])
        has_y = any(kw in line_lower for kw in keyword_groups['center_y'])
        if has_des and has_x and has_y:
            header_line = line.strip()
            header_index = i
            break

    if header_line is None:
        raise RuntimeError("Не удалось найти заголовок с Designator/refdes, Center-X/symbol_x, Center-Y/symbol_y")

    headers = split_line(header_line, delimiter)
    if headers and headers[0].startswith('#'):
        headers[0] = headers[0][1:].strip()

    data = []
    for line in lines[header_index+1:]:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('#'):
            continue
        parts = split_line(line_clean, delimiter)
        if len(parts) >= len(headers):
            data.append(parts[:len(headers)])
        elif len(parts) > 0:
            data.append(parts + [''] * (len(headers) - len(parts)))

    if not data:
        raise RuntimeError("Нет данных для обработки")

    df = pd.DataFrame(data, columns=headers)

    column_keywords = {
        'Designator': ['designator', 'refdes'],
        'Center-X(mm)': ['center-x', 'symbol_x'],
        'Center-Y(mm)': ['center-y', 'symbol_y'],
        'Rotation': ['rotation']
    }
    rename_dict = {}
    found_info = {}
    for target, keywords in column_keywords.items():
        found_col = find_column_by_keywords(df, keywords)
        if found_col is not None:
            rename_dict[found_col] = target
            found_info[target] = found_col
    df.rename(columns=rename_dict, inplace=True)

    required = ['Designator', 'Center-X(mm)', 'Center-Y(mm)']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"Не удалось найти обязательные столбцы: {missing}")

    # Обработка слоя (улучшенная нормализация)
    mirror_col = find_column_by_keywords(df, ['mirror', 'mirrored'])
    if mirror_col is not None:
        df.rename(columns={mirror_col: 'Mirror'}, inplace=True)
        df['Layer'] = df['Mirror'].apply(normalize_layer_from_mirror)
    else:
        layer_col = find_column_by_keywords(df, ['layer', 'side', 'board side'])
        if layer_col is not None:
            df.rename(columns={layer_col: 'Layer'}, inplace=True)
            df['Layer'] = df['Layer'].apply(normalize_layer_general)
        else:
            df['Layer'] = 'TopLayer'

    # Определение единиц измерения
    orig_x = found_info.get('Center-X(mm)', '')
    orig_y = found_info.get('Center-Y(mm)', '')
    is_mil_x = '(mil)' in orig_x.lower()
    is_mil_y = '(mil)' in orig_y.lower()
    units_mm = any('uunits' in line.lower() and 'millimeters' in line.lower() for line in lines)
    if units_mm:
        is_mil_x = False
        is_mil_y = False

    df['Center-X(mm)'] = safe_convert(df['Center-X(mm)'], is_mil=is_mil_x)
    df['Center-Y(mm)'] = safe_convert(df['Center-Y(mm)'], is_mil=is_mil_y)
    df['Center-X(mm)'] = pd.to_numeric(df['Center-X(mm)'], errors='coerce')
    df['Center-Y(mm)'] = pd.to_numeric(df['Center-Y(mm)'], errors='coerce')

    if 'Rotation' in df.columns:
        try:
            df['Rotation'] = pd.to_numeric(df['Rotation'].astype(str).str.replace(',', '.'), errors='coerce')
        except:
            pass

    result_columns = ['Designator', 'Layer', 'Center-X(mm)', 'Center-Y(mm)']
    if 'Rotation' in df.columns:
        result_columns.append('Rotation')
    df = df[result_columns]

    if 'Designator' in df.columns:
        df.sort_values(by='Designator', inplace=True)

    base_name = os.path.splitext(original_filename)[0]
    safe_base_name = re.sub(r'[\\/*?:"<>|]', '_', base_name)
    output_dir = tempfile.gettempdir()
    output_path = os.path.join(output_dir, f"{safe_base_name}_converted.xlsx")

    df.to_excel(output_path, index=False)
    return output_path
