# Базовый образ Python
FROM python:3.11-slim

# Создаём рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости (нужны для xlwings и openpyxl)
RUN apt-get update && apt-get install -y \
    gcc \
    libgl1-mesa-glx \
    libxcb-xinerama0 \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Отключаем буферизацию вывода Python
ENV PYTHONUNBUFFERED=1

# Команда запуска бота
CMD ["python", "SMT_Creator_MegaTool_bot.py"]