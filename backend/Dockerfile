# The Taste API. Catalogues are mounted, not baked in; accounts and ratings live in Postgres:
#   docker build -t taste-api backend
#   docker run -p 127.0.0.1:8000:8000 -v "$PWD/data:/data:ro" --env-file .env taste-api
# (or docker compose up, from the repo root). Migrations run on start.
# Behind a proxy or load balancer, set FORWARDED_ALLOW_IPS to its address or network (e.g. the
# VPC's 10.0.0.0/16) so client IPs come from X-Forwarded-For; never "*".
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY taste ./taste
COPY migrations ./migrations
RUN pip install --no-cache-dir . && useradd --system --uid 10001 --no-create-home taste
USER taste
ENV TASTE_DATA_DIR=/data
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn taste.api.app:app --host 0.0.0.0 --port 8000 --proxy-headers"]
