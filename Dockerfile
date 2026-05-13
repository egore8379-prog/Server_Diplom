# 1. Легкий Python
FROM python:3.9-slim

# 2. Робоча папка
WORKDIR /app

# 3. Встановлюємо бібліотеки
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Копіюємо код
COPY . .

# 5. Порт
EXPOSE 8000

# 6. Запуск (main:app)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
