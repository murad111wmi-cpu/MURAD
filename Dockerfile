FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . .
RUN if [ -d .wheels ]; then pip install --no-cache-dir --no-index --find-links=.wheels -r requirements.txt; else pip install --no-cache-dir -r requirements.txt; fi \
    && rm -rf .wheels && chmod -R a+rX /app && useradd --uid 10001 --create-home app \
    && mkdir -p /app/data /app/media /app/staticfiles \
    && chown -R app:app /app/data /app/media /app/staticfiles
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
