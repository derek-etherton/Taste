# The Taste API. Catalogues are mounted, not baked in; accounts and ratings live in Postgres:
#   docker build -t taste-api backend
#   docker run -p 8000:8000 -v "$PWD/data:/data" -e TASTE_DATABASE_URL=postgresql+psycopg://... taste-api
# (or docker compose up, from the repo root). Migrations run on start.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY taste ./taste
COPY migrations ./migrations
RUN pip install --no-cache-dir .
ENV TASTE_DATA_DIR=/data
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn taste.api.app:app --host 0.0.0.0 --port 8000"]
