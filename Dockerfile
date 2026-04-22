FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# --upgrade lets pip bump transitive deps that were pinned too low on Windows
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

EXPOSE 8000 8001

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
