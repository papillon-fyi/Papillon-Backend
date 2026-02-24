FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for numpy/onnxruntime performance)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy project files into the container
COPY . .

# Ensure models directory exists and copy ONNX model (if not already copied)
RUN mkdir -p /app/models

# Install dependencies (includes ONNX + Transformers)
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Cloud Run will send traffic to
EXPOSE 8080

# Use the $PORT environment variable provided by Cloud Run (default to 8080 for local dev)
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
