# The Taste API. Data (catalogues and profiles) is mounted, not baked in:
#   docker build -t taste-api backend
#   docker run -p 8000:8000 -v "$PWD/data:/data" -e OLLAMA_URL=http://host.docker.internal:11434 taste-api
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY taste ./taste
RUN pip install --no-cache-dir .
ENV TASTE_DATA_DIR=/data
EXPOSE 8000
CMD ["uvicorn", "taste.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
