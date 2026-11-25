FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock .
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
