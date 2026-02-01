### Standalone Spleeter API Service
### Lightweight audio separation service that n8n can call via HTTP
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Spleeter and Flask for API
RUN pip install --no-cache-dir \
    spleeter==2.4.0 \
    flask==3.0.0 \
    flask-cors==4.0.0

# Create app directory
WORKDIR /app

# Create directories for processing
RUN mkdir -p /app/uploads /app/outputs

# Copy API server script (we'll create this)
COPY spleeter_api.py /app/

# Pre-download Spleeter models to avoid first-use delay
# This downloads ~200MB of models
RUN python -c "from spleeter.separator import Separator; Separator('spleeter:4stems')" || true

# Environment variables
ENV FLASK_APP=spleeter_api.py
ENV PYTHONUNBUFFERED=1
ENV UPLOAD_FOLDER=/app/uploads
ENV OUTPUT_FOLDER=/app/outputs

# Expose API port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')"

# Run Flask API
CMD ["python", "spleeter_api.py"]
