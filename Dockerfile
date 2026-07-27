# Базовый образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости (нужны для xlwings и openpyxl)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создаём рабочую директорию
WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Отключаем буферизацию вывода Python
ENV PYTHONUNBUFFERED=1

# Команда запуска бота
CMD ["python", "SMT_Creator_MegaTool_bot.py"]