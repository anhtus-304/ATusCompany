FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ai ai
COPY backend backend
COPY frontend frontend
COPY workspace/README.md workspace/README.md
ENV VTD_WORKSPACE=/data/workspace VTD_DB=/data/vtd.sqlite3
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
