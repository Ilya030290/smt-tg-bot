import re
import pandas as pd

def clean_article_name(value):
    """Очищает название компонента от запятых и пробелов."""
    if pd.isna(value):
        return value
    str_value = str(value)
    str_value = str_value.replace(',', '.')
    str_value = str_value.replace(' ', '_')
    return str_value
