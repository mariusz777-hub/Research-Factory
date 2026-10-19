FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
COPY config ./config
COPY alembic ./alembic
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "research_factory.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
