FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home appuser
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER appuser
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} --timeout 90 app:app"]