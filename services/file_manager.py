import os
import tempfile
from telegram import Document

async def download_file(document: Document) -> str:
    """
    Скачивает файл от пользователя во временную директорию.
    Возвращает путь к скачанному файлу.
    """
    file = await document.get_file()
    suffix = os.path.splitext(document.file_name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    await file.download_to_drive(tmp.name)
    return tmp.name

def delete_file(file_path: str) -> None:
    """Безопасно удаляет файл."""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except Exception:
        pass

def get_temp_path(prefix: str = "", suffix: str = "") -> str:
    """Возвращает путь к временному файлу с заданными префиксом и суффиксом."""
    return tempfile.NamedTemporaryFile(delete=False, prefix=prefix, suffix=suffix).name
