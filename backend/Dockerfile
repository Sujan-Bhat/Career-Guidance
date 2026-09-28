FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# CPU wheels first so the ml package's torch>=2.1 resolves without CUDA deps
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Part B + Part A installed editable: config/artifact paths resolve next to the
# package source (ml/configs, ml/artifacts), which the backend reads at runtime
COPY ml ml
COPY llm_gateway llm_gateway
RUN pip install --no-cache-dir -e ml && \
    pip install --no-cache-dir -e llm_gateway && \
    pip install --no-cache-dir openai

# knowledge-graph seed + Mongo seeder (first run: python /app/data/seeds/seed_mongo.py)
COPY data data
COPY backend backend

WORKDIR /app/backend

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
