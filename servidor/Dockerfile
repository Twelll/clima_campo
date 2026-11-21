FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --gid 10001 estacao \
    && useradd --uid 10001 --gid estacao --no-create-home estacao \
    && mkdir /dados \
    && chown estacao:estacao /dados

WORKDIR /app
COPY --chown=estacao:estacao app/ ./app/
USER estacao:estacao

EXPOSE 8080
CMD ["python", "-m", "app", "--host", "0.0.0.0", "--port", "8080", "--db", "/dados/dados.sqlite3"]
