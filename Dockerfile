FROM python:3.11-slim

WORKDIR /app

# Ensure we don't bake in credentials
ENV GEMINI_API_KEY=""

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Start the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
