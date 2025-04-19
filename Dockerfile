# Вибираємо Python 3.11 (або новішу версію)
FROM python:3.11
# Встановлюємо робочу директорію
WORKDIR /app
# Копіюємо залежності
COPY requirements.txt requirements.txt
# Встановлюємо залежності
RUN pip install --no-cache-dir -r requirements.txt
# Копіюємо решту коду бота
COPY . .
# Запускаємо бота
CMD ["python", "bot.py"]