FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY knowledge_base/ knowledge_base/
COPY scripts/ scripts/
WORKDIR /app/backend
ENV HCC_KNOWLEDGE_BASE_DIR=/app/knowledge_base
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
