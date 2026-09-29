FROM python:3.10-slim

# Устанавливаем ffmpeg для конвертации голосовых
RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app

# Копируем список библиотек и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем сам код бота
COPY . .

# Команда для запуска
CMD ["python", "bot.py"]